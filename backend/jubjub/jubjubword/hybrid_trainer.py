"""
Training infrastructure for Markov-LSTM hybrid models

Includes:
- Data preparation from corpus
- Training loop with validation
- Early stopping
- Progress tracking
- Model checkpointing
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from typing import List, Tuple, Optional
import numpy as np
import logging
from pathlib import Path
from tqdm import tqdm
import json

from .hybrid import CharLSTM, CharVocabulary

logger = logging.getLogger(__name__)


class WordDataset(Dataset):
    """
    Dataset for character-level word generation

    Converts words into sequences of character indices with start/end markers
    """

    def __init__(self, words: List[str], vocabulary: CharVocabulary,
                 max_length: int = 20):
        self.words = words
        self.vocab = vocabulary
        self.max_length = max_length

        # Prepare sequences
        self.sequences = []
        for word in words:
            # Add start/end markers
            word_with_markers = vocabulary.START_TOKEN + word.lower() + vocabulary.END_TOKEN

            # Convert to indices
            indices = vocabulary.encode(word_with_markers)

            # Truncate if too long
            if len(indices) > max_length:
                indices = indices[:max_length]

            self.sequences.append(indices)

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        """
        Returns:
            input: sequence without last character
            target: sequence without first character
        """
        seq = self.sequences[idx]

        # input: [START, a, b, c]
        # target: [a, b, c, END]
        input_seq = torch.tensor(seq[:-1], dtype=torch.long)
        target_seq = torch.tensor(seq[1:], dtype=torch.long)

        return input_seq, target_seq


def collate_fn(batch):
    """
    Collate function to pad sequences to same length in batch
    """
    inputs, targets = zip(*batch)

    # Find max length in batch
    max_len = max(len(inp) for inp in inputs)

    # Pad sequences
    padded_inputs = []
    padded_targets = []

    for inp, tgt in zip(inputs, targets):
        pad_len = max_len - len(inp)
        padded_inp = torch.cat([inp, torch.zeros(pad_len, dtype=torch.long)])
        padded_tgt = torch.cat([tgt, torch.zeros(pad_len, dtype=torch.long)])

        padded_inputs.append(padded_inp)
        padded_targets.append(padded_tgt)

    return torch.stack(padded_inputs), torch.stack(padded_targets)


class LSTMTrainer:
    """
    Trainer for CharLSTM with early stopping and checkpointing
    """

    def __init__(self, model: CharLSTM, vocabulary: CharVocabulary,
                 learning_rate: float = 0.001,
                 device: str = 'cpu'):
        self.model = model.to(device)
        self.vocab = vocabulary
        self.device = device

        self.optimizer = optim.Adam(model.parameters(), lr=learning_rate)
        self.criterion = nn.CrossEntropyLoss(ignore_index=vocabulary.char2idx[vocabulary.PAD_TOKEN])

        self.train_losses = []
        self.val_losses = []
        self.best_val_loss = float('inf')
        self.epochs_without_improvement = 0

    def train_epoch(self, dataloader: DataLoader) -> float:
        """Train for one epoch"""
        self.model.train()
        total_loss = 0
        num_batches = 0

        for inputs, targets in dataloader:
            inputs = inputs.to(self.device)
            targets = targets.to(self.device)

            # Zero gradients
            self.optimizer.zero_grad()

            # Forward pass
            logits, _ = self.model(inputs)

            # Reshape for loss calculation
            # logits: (batch, seq_len, vocab_size)
            # targets: (batch, seq_len)
            logits_flat = logits.view(-1, logits.size(-1))
            targets_flat = targets.view(-1)

            # Calculate loss
            loss = self.criterion(logits_flat, targets_flat)

            # Backward pass
            loss.backward()

            # Clip gradients to prevent exploding gradients
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)

            # Update weights
            self.optimizer.step()

            total_loss += loss.item()
            num_batches += 1

        return total_loss / num_batches

    def validate(self, dataloader: DataLoader) -> float:
        """Validate model"""
        self.model.eval()
        total_loss = 0
        num_batches = 0

        with torch.no_grad():
            for inputs, targets in dataloader:
                inputs = inputs.to(self.device)
                targets = targets.to(self.device)

                # Forward pass
                logits, _ = self.model(inputs)

                # Calculate loss
                logits_flat = logits.view(-1, logits.size(-1))
                targets_flat = targets.view(-1)
                loss = self.criterion(logits_flat, targets_flat)

                total_loss += loss.item()
                num_batches += 1

        return total_loss / num_batches

    def train(self, train_words: List[str], val_words: List[str],
              epochs: int = 50, batch_size: int = 32,
              early_stopping_patience: int = 5,
              checkpoint_dir: Optional[Path] = None) -> Dict:
        """
        Train the LSTM model

        Args:
            train_words: Training corpus
            val_words: Validation corpus
            epochs: Maximum number of epochs
            batch_size: Batch size
            early_stopping_patience: Stop if no improvement for N epochs
            checkpoint_dir: Directory to save checkpoints

        Returns:
            Training history dictionary
        """
        # Create datasets
        train_dataset = WordDataset(train_words, self.vocab)
        val_dataset = WordDataset(val_words, self.vocab)

        train_loader = DataLoader(train_dataset, batch_size=batch_size,
                                 shuffle=True, collate_fn=collate_fn)
        val_loader = DataLoader(val_dataset, batch_size=batch_size,
                               shuffle=False, collate_fn=collate_fn)

        logger.info(f"Training on {len(train_words)} words, validating on {len(val_words)} words")
        logger.info(f"Vocabulary size: {len(self.vocab)}")
        logger.info(f"Device: {self.device}")

        # Training loop
        for epoch in range(epochs):
            # Train
            train_loss = self.train_epoch(train_loader)
            self.train_losses.append(train_loss)

            # Validate
            val_loss = self.validate(val_loader)
            self.val_losses.append(val_loss)

            # Log progress
            logger.info(f"Epoch {epoch+1}/{epochs} - "
                       f"Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}")

            # Check for improvement
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.epochs_without_improvement = 0

                # Save checkpoint
                if checkpoint_dir:
                    self._save_checkpoint(checkpoint_dir / 'best_model.pt')

            else:
                self.epochs_without_improvement += 1

            # Early stopping
            if self.epochs_without_improvement >= early_stopping_patience:
                logger.info(f"Early stopping triggered after {epoch+1} epochs")
                break

        # Load best model
        if checkpoint_dir and (checkpoint_dir / 'best_model.pt').exists():
            self._load_checkpoint(checkpoint_dir / 'best_model.pt')

        return {
            'train_losses': self.train_losses,
            'val_losses': self.val_losses,
            'best_val_loss': self.best_val_loss,
            'epochs_trained': len(self.train_losses)
        }

    def _save_checkpoint(self, path: Path):
        """Save model checkpoint"""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'train_losses': self.train_losses,
            'val_losses': self.val_losses,
            'best_val_loss': self.best_val_loss
        }, path)

    def _load_checkpoint(self, path: Path):
        """Load model checkpoint"""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])


def prepare_corpus_for_training(words: List[str], train_split: float = 0.9) -> Tuple[List[str], List[str]]:
    """
    Split corpus into train/validation sets

    Args:
        words: Full corpus
        train_split: Fraction for training (rest for validation)

    Returns:
        (train_words, val_words)
    """
    # Shuffle
    words = list(words)
    np.random.shuffle(words)

    # Split
    split_idx = int(len(words) * train_split)
    train_words = words[:split_idx]
    val_words = words[split_idx:]

    return train_words, val_words


def train_lstm_for_corpus(corpus_words: List[str],
                          hidden_size: int = 64,
                          num_layers: int = 2,
                          epochs: int = 50,
                          batch_size: int = 32,
                          learning_rate: float = 0.001,
                          output_dir: Optional[Path] = None,
                          device: str = 'cpu') -> Tuple[CharLSTM, CharVocabulary, Dict]:
    """
    End-to-end training pipeline for a corpus

    Args:
        corpus_words: List of words from corpus
        hidden_size: LSTM hidden size
        num_layers: Number of LSTM layers
        epochs: Maximum epochs
        batch_size: Batch size
        learning_rate: Learning rate
        output_dir: Where to save model
        device: 'cpu' or 'cuda'

    Returns:
        (trained_model, vocabulary, training_history)
    """
    # Build vocabulary
    logger.info("Building vocabulary...")
    vocab = CharVocabulary()
    vocab.build_from_corpus(corpus_words)
    logger.info(f"Vocabulary size: {len(vocab)}")

    # Split data
    train_words, val_words = prepare_corpus_for_training(corpus_words)
    logger.info(f"Train: {len(train_words)} words, Val: {len(val_words)} words")

    # Create model
    model = CharLSTM(
        vocab_size=len(vocab),
        hidden_size=hidden_size,
        num_layers=num_layers
    )

    # Count parameters
    num_params = sum(p.numel() for p in model.parameters())
    logger.info(f"Model parameters: {num_params:,}")

    # Estimate model size
    model_size_bytes = num_params * 4  # Assuming float32
    model_size_kb = model_size_bytes / 1024
    logger.info(f"Estimated model size: {model_size_kb:.1f} KB")

    # Train
    trainer = LSTMTrainer(model, vocab, learning_rate=learning_rate, device=device)
    history = trainer.train(
        train_words=train_words,
        val_words=val_words,
        epochs=epochs,
        batch_size=batch_size,
        checkpoint_dir=output_dir
    )

    # Save final model
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save model
        torch.save({
            'model_state_dict': model.state_dict(),
            'vocab_size': len(vocab),
            'hidden_size': hidden_size,
            'num_layers': num_layers
        }, output_dir / 'lstm_model.pt')

        # Save vocabulary
        vocab.save(output_dir / 'vocabulary.json')

        # Save training history
        with open(output_dir / 'training_history.json', 'w') as f:
            json.dump(history, f, indent=2)

        logger.info(f"Model saved to {output_dir}")

    return model, vocab, history
