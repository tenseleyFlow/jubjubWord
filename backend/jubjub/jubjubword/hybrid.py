"""
Markov-LSTM Hybrid Word Generator

Novel approach: Confidence-weighted ensemble that adapts per-character based on
model uncertainty. Combines interpretable Markov chains with learned neural patterns.

Key innovations:
1. Adaptive ensemble weighting based on prediction confidence
2. Character-level LSTM learns phonotactic patterns
3. Markov provides safety fallback for uncertain predictions
4. Corpus-specific fine-tuning
5. Tiny models (~50-100KB) suitable for production

Potential research contribution:
"Confidence-Weighted Ensembles for Controllable Nonsense Word Generation"
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple
import numpy as np
import logging
from pathlib import Path
from collections import Counter
import json

logger = logging.getLogger(__name__)


class CharLSTM(nn.Module):
    """
    Lightweight character-level LSTM for phonotactic pattern learning.

    Architecture:
        - Embedding: vocab_size -> hidden_size
        - LSTM: hidden_size -> hidden_size (2 layers)
        - Output: hidden_size -> vocab_size

    Size: ~50-100KB depending on hidden_size
    """

    def __init__(self, vocab_size: int, hidden_size: int = 64, num_layers: int = 2,
                 dropout: float = 0.2):
        super().__init__()

        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.embedding = nn.Embedding(vocab_size, hidden_size)
        self.lstm = nn.LSTM(
            hidden_size,
            hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True
        )
        self.fc = nn.Linear(hidden_size, vocab_size)

        # Initialize weights
        self._init_weights()

    def _init_weights(self):
        """Xavier initialization for better convergence"""
        for name, param in self.named_parameters():
            if 'weight' in name:
                if 'lstm' in name:
                    nn.init.orthogonal_(param)
                else:
                    nn.init.xavier_uniform_(param)
            elif 'bias' in name:
                nn.init.constant_(param, 0.0)

    def forward(self, x, hidden=None):
        """
        Forward pass

        Args:
            x: (batch, seq_len) character indices
            hidden: Optional (h, c) tuple for LSTM state

        Returns:
            logits: (batch, seq_len, vocab_size)
            hidden: Updated LSTM state
        """
        embedded = self.embedding(x)  # (batch, seq_len, hidden_size)
        output, hidden = self.lstm(embedded, hidden)  # (batch, seq_len, hidden_size)
        logits = self.fc(output)  # (batch, seq_len, vocab_size)

        return logits, hidden

    def init_hidden(self, batch_size: int, device='cpu'):
        """Initialize hidden state"""
        h = torch.zeros(self.num_layers, batch_size, self.hidden_size).to(device)
        c = torch.zeros(self.num_layers, batch_size, self.hidden_size).to(device)
        return (h, c)


class CharVocabulary:
    """
    Character vocabulary with special tokens for word boundaries
    """

    def __init__(self):
        self.char2idx: Dict[str, int] = {}
        self.idx2char: Dict[int, str] = {}

        # Special tokens
        self.PAD_TOKEN = '<PAD>'
        self.START_TOKEN = '^'
        self.END_TOKEN = '$'
        self.UNK_TOKEN = '<UNK>'

        # Initialize with special tokens
        self._add_char(self.PAD_TOKEN)
        self._add_char(self.START_TOKEN)
        self._add_char(self.END_TOKEN)
        self._add_char(self.UNK_TOKEN)

    def _add_char(self, char: str):
        """Add character to vocabulary"""
        if char not in self.char2idx:
            idx = len(self.char2idx)
            self.char2idx[char] = idx
            self.idx2char[idx] = char

    def build_from_corpus(self, words: List[str]):
        """Build vocabulary from corpus words"""
        for word in words:
            for char in word.lower():
                self._add_char(char)

    def encode(self, text: str) -> List[int]:
        """Convert text to indices"""
        return [self.char2idx.get(c, self.char2idx[self.UNK_TOKEN]) for c in text]

    def decode(self, indices: List[int]) -> str:
        """Convert indices to text"""
        return ''.join([self.idx2char.get(idx, self.UNK_TOKEN) for idx in indices])

    def __len__(self):
        return len(self.char2idx)

    def save(self, path: Path):
        """Save vocabulary to JSON"""
        with open(path, 'w') as f:
            json.dump({
                'char2idx': self.char2idx,
                'idx2char': {int(k): v for k, v in self.idx2char.items()}
            }, f)

    def load(self, path: Path):
        """Load vocabulary from JSON"""
        with open(path, 'r') as f:
            data = json.load(f)
            self.char2idx = data['char2idx']
            self.idx2char = {int(k): v for k, v in data['idx2char'].items()}


class HybridMarkovLSTM:
    """
    Novel hybrid generator that combines Markov chains with LSTM using
    confidence-weighted ensemble.

    Key innovation: Per-character adaptive weighting based on model confidence.
    """

    def __init__(self, markov_instance, lstm_model: CharLSTM,
                 vocabulary: CharVocabulary,
                 base_markov_weight: float = 0.6,
                 base_lstm_weight: float = 0.4,
                 confidence_adaptation: bool = True):
        """
        Initialize hybrid generator

        Args:
            markov_instance: Trained Markov chain
            lstm_model: Trained CharLSTM
            vocabulary: Character vocabulary
            base_markov_weight: Base weight for Markov (0-1)
            base_lstm_weight: Base weight for LSTM (0-1)
            confidence_adaptation: Whether to adapt weights based on confidence
        """
        self.markov = markov_instance
        self.lstm = lstm_model
        self.vocab = vocabulary

        self.base_markov_weight = base_markov_weight
        self.base_lstm_weight = base_lstm_weight
        self.confidence_adaptation = confidence_adaptation

        self.lstm.eval()  # Set to eval mode
        self.device = next(self.lstm.parameters()).device

    def _get_markov_distribution(self, state: str) -> Dict[str, float]:
        """
        Get character probability distribution from Markov chain

        Returns:
            Dictionary mapping characters to probabilities
        """
        char_counter = self.markov.transitions.get(state, Counter())

        if not char_counter:
            # Uniform distribution if no transitions
            return {}

        total = sum(char_counter.values())
        return {char: count / total for char, count in char_counter.items()}

    def _get_lstm_distribution(self, context: List[int], temperature: float = 1.0) -> Tuple[Dict[str, float], float]:
        """
        Get character probability distribution from LSTM

        Returns:
            (distribution dict, confidence score)
        """
        with torch.no_grad():
            # Prepare input
            x = torch.tensor([context], dtype=torch.long).to(self.device)

            # Get predictions
            logits, _ = self.lstm(x)
            logits = logits[0, -1, :]  # Last timestep

            # Apply temperature
            logits = logits / temperature
            probs = F.softmax(logits, dim=0)

            # Calculate confidence (entropy-based)
            entropy = -torch.sum(probs * torch.log(probs + 1e-10))
            max_entropy = np.log(len(probs))
            confidence = 1.0 - (entropy / max_entropy).item()

            # Convert to dictionary
            distribution = {}
            for idx, prob in enumerate(probs.cpu().numpy()):
                char = self.vocab.idx2char.get(idx)
                if char and char not in [self.vocab.PAD_TOKEN, self.vocab.UNK_TOKEN]:
                    distribution[char] = float(prob)

            return distribution, confidence

    def _combine_distributions(self, markov_dist: Dict[str, float],
                               lstm_dist: Dict[str, float],
                               lstm_confidence: float) -> Dict[str, float]:
        """
        Combine Markov and LSTM distributions with adaptive weighting

        Innovation: Weight based on LSTM confidence
        - High confidence: Trust LSTM more
        - Low confidence: Fall back to Markov
        """
        if self.confidence_adaptation:
            # Adaptive weighting based on LSTM confidence
            # High confidence -> more LSTM, low confidence -> more Markov
            lstm_weight = self.base_lstm_weight * (0.5 + 0.5 * lstm_confidence)
            markov_weight = 1.0 - lstm_weight
        else:
            # Fixed weights
            lstm_weight = self.base_lstm_weight
            markov_weight = self.base_markov_weight

        # Get all possible characters
        all_chars = set(markov_dist.keys()) | set(lstm_dist.keys())

        # Combine probabilities
        combined = {}
        for char in all_chars:
            markov_prob = markov_dist.get(char, 0.0)
            lstm_prob = lstm_dist.get(char, 0.0)

            combined[char] = markov_weight * markov_prob + lstm_weight * lstm_prob

        # Normalize
        total = sum(combined.values())
        if total > 0:
            combined = {char: prob / total for char, prob in combined.items()}

        return combined

    def generate(self, max_length: int = 10, min_length: int = 3,
                 temperature: float = 1.0, seed: Optional[str] = None) -> Tuple[str, Dict]:
        """
        Generate a word using hybrid ensemble

        Returns:
            (word, metadata dict with generation info)
        """
        # Prepare starting context
        if seed:
            context_str = self.vocab.START_TOKEN * self.markov.n + seed.lower()
        else:
            context_str = self.vocab.START_TOKEN * self.markov.n

        context_indices = self.vocab.encode(context_str)

        output_chars = []
        metadata = {
            'markov_influence': [],
            'lstm_influence': [],
            'lstm_confidence': [],
            'characters': []
        }

        attempts = 0
        max_attempts = max_length * 3

        while len(output_chars) < max_length and attempts < max_attempts:
            attempts += 1

            # Get Markov state (last n characters)
            markov_state = context_str[-self.markov.n:]

            # Get distributions from both models
            markov_dist = self._get_markov_distribution(markov_state)
            lstm_dist, lstm_confidence = self._get_lstm_distribution(context_indices[-20:], temperature)

            # Combine distributions
            combined_dist = self._combine_distributions(markov_dist, lstm_dist, lstm_confidence)

            if not combined_dist:
                break

            # Sample from combined distribution
            chars, probs = zip(*combined_dist.items())
            next_char = np.random.choice(chars, p=probs)

            # Check for end marker
            if next_char == self.vocab.END_TOKEN:
                if len(output_chars) >= min_length:
                    break
                # Try again without end token
                combined_dist_no_end = {c: p for c, p in combined_dist.items() if c != self.vocab.END_TOKEN}
                if not combined_dist_no_end:
                    break
                total = sum(combined_dist_no_end.values())
                combined_dist_no_end = {c: p/total for c, p in combined_dist_no_end.items()}
                chars, probs = zip(*combined_dist_no_end.items())
                next_char = np.random.choice(chars, p=probs)

            # Skip start marker in output
            if next_char != self.vocab.START_TOKEN:
                output_chars.append(next_char)

                # Record metadata
                metadata['characters'].append(next_char)
                metadata['lstm_confidence'].append(lstm_confidence)

                # Calculate actual influence (how much each model agreed)
                markov_preferred = markov_dist.get(next_char, 0.0)
                lstm_preferred = lstm_dist.get(next_char, 0.0)
                metadata['markov_influence'].append(markov_preferred)
                metadata['lstm_influence'].append(lstm_preferred)

            # Update context
            context_str += next_char
            context_indices.append(self.vocab.char2idx.get(next_char, self.vocab.char2idx[self.vocab.UNK_TOKEN]))

        word = ''.join(output_chars)

        # Add summary statistics to metadata
        if metadata['lstm_confidence']:
            metadata['avg_lstm_confidence'] = np.mean(metadata['lstm_confidence'])
            metadata['avg_markov_influence'] = np.mean(metadata['markov_influence'])
            metadata['avg_lstm_influence'] = np.mean(metadata['lstm_influence'])

        return word, metadata

    def save(self, directory: Path):
        """Save hybrid model components"""
        directory.mkdir(parents=True, exist_ok=True)

        # Save LSTM
        torch.save({
            'model_state_dict': self.lstm.state_dict(),
            'vocab_size': self.lstm.vocab_size,
            'hidden_size': self.lstm.hidden_size,
            'num_layers': self.lstm.num_layers
        }, directory / 'lstm_model.pt')

        # Save vocabulary
        self.vocab.save(directory / 'vocabulary.json')

        # Save hyperparameters
        with open(directory / 'hybrid_config.json', 'w') as f:
            json.dump({
                'base_markov_weight': self.base_markov_weight,
                'base_lstm_weight': self.base_lstm_weight,
                'confidence_adaptation': self.confidence_adaptation
            }, f)

        logger.info(f"Hybrid model saved to {directory}")

    @classmethod
    def load(cls, directory: Path, markov_instance):
        """Load hybrid model from disk"""
        # Load LSTM
        lstm_checkpoint = torch.load(directory / 'lstm_model.pt', map_location='cpu')
        lstm = CharLSTM(
            vocab_size=lstm_checkpoint['vocab_size'],
            hidden_size=lstm_checkpoint['hidden_size'],
            num_layers=lstm_checkpoint['num_layers']
        )
        lstm.load_state_dict(lstm_checkpoint['model_state_dict'])

        # Load vocabulary
        vocab = CharVocabulary()
        vocab.load(directory / 'vocabulary.json')

        # Load config
        with open(directory / 'hybrid_config.json', 'r') as f:
            config = json.load(f)

        return cls(markov_instance, lstm, vocab, **config)
