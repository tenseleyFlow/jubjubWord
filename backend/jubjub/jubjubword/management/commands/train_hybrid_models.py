"""
Management command to train hybrid Markov-LSTM models

Usage:
    # Train for specific corpus
    python manage.py train_hybrid_models --corpus scifi

    # Train for all corpora
    python manage.py train_hybrid_models --all

    # Custom hyperparameters
    python manage.py train_hybrid_models --corpus scifi --hidden-size 128 --epochs 100

    # GPU training
    python manage.py train_hybrid_models --corpus scifi --device cuda
"""

from django.core.management.base import BaseCommand
from jubjub.jubjubword.models import Corpus
from jubjub.jubjubword.markov import get_markov_instance
from jubjub.jubjubword.hybrid_trainer import train_lstm_for_corpus
from jubjub.jubjubword.hybrid import HybridMarkovLSTM
from pathlib import Path
from django.conf import settings
import logging
import torch

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Train hybrid Markov-LSTM models for word generation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--corpus',
            type=str,
            help='Specific corpus slug to train (e.g., scifi, fantasy)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Train models for all active corpora',
        )
        parser.add_argument(
            '--hidden-size',
            type=int,
            default=64,
            help='LSTM hidden size (default: 64)',
        )
        parser.add_argument(
            '--num-layers',
            type=int,
            default=2,
            help='Number of LSTM layers (default: 2)',
        )
        parser.add_argument(
            '--epochs',
            type=int,
            default=50,
            help='Maximum training epochs (default: 50)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=32,
            help='Training batch size (default: 32)',
        )
        parser.add_argument(
            '--learning-rate',
            type=float,
            default=0.001,
            help='Learning rate (default: 0.001)',
        )
        parser.add_argument(
            '--device',
            type=str,
            default='cpu',
            choices=['cpu', 'cuda'],
            help='Device to train on (default: cpu)',
        )
        parser.add_argument(
            '--markov-weight',
            type=float,
            default=0.6,
            help='Base Markov weight in ensemble (default: 0.6)',
        )
        parser.add_argument(
            '--lstm-weight',
            type=float,
            default=0.4,
            help='Base LSTM weight in ensemble (default: 0.4)',
        )

    def handle(self, *args, **options):
        corpus_slug = options.get('corpus')
        train_all = options.get('all')
        hidden_size = options.get('hidden_size')
        num_layers = options.get('num_layers')
        epochs = options.get('epochs')
        batch_size = options.get('batch_size')
        learning_rate = options.get('learning_rate')
        device = options.get('device')
        markov_weight = options.get('markov_weight')
        lstm_weight = options.get('lstm_weight')

        # Check CUDA availability
        if device == 'cuda' and not torch.cuda.is_available():
            self.stdout.write(self.style.WARNING('CUDA not available, using CPU'))
            device = 'cpu'

        # Get corpora to train
        if train_all:
            corpora = Corpus.objects.filter(is_active=True)
        elif corpus_slug:
            try:
                corpora = [Corpus.objects.get(slug=corpus_slug, is_active=True)]
            except Corpus.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Corpus "{corpus_slug}" not found'))
                return
        else:
            self.stdout.write(self.style.ERROR('Please specify --corpus or --all'))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'\n🚀 Training hybrid models for {len(corpora)} corpora\n'
            )
        )

        self.stdout.write(f'Hyperparameters:')
        self.stdout.write(f'  Hidden size: {hidden_size}')
        self.stdout.write(f'  Num layers: {num_layers}')
        self.stdout.write(f'  Epochs: {epochs}')
        self.stdout.write(f'  Batch size: {batch_size}')
        self.stdout.write(f'  Learning rate: {learning_rate}')
        self.stdout.write(f'  Device: {device}')
        self.stdout.write(f'  Markov weight: {markov_weight}')
        self.stdout.write(f'  LSTM weight: {lstm_weight}\n')

        # Output directory
        models_dir = Path(settings.BASE_DIR) / 'jubjub' / 'jubjubword' / 'hybrid_models'

        for corpus in corpora:
            self.stdout.write(f'\n{"="*60}')
            self.stdout.write(self.style.SUCCESS(f'Training: {corpus.name} ({corpus.slug})'))
            self.stdout.write(f'{"="*60}\n')

            # Load corpus words
            words = corpus.get_words_list()
            self.stdout.write(f'Corpus size: {len(words)} words')

            if len(words) < 100:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Corpus too small ({len(words)} words), skipping')
                )
                continue

            # Output directory for this corpus
            output_dir = models_dir / corpus.slug
            output_dir.mkdir(parents=True, exist_ok=True)

            try:
                # Train LSTM
                self.stdout.write('\n📚 Training LSTM...')
                lstm_model, vocab, history = train_lstm_for_corpus(
                    corpus_words=words,
                    hidden_size=hidden_size,
                    num_layers=num_layers,
                    epochs=epochs,
                    batch_size=batch_size,
                    learning_rate=learning_rate,
                    output_dir=output_dir,
                    device=device
                )

                # Training summary
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✓ Training complete!'
                    )
                )
                self.stdout.write(f'  Epochs trained: {history["epochs_trained"]}')
                self.stdout.write(f'  Best val loss: {history["best_val_loss"]:.4f}')
                self.stdout.write(f'  Final train loss: {history["train_losses"][-1]:.4f}')

                # Create hybrid model
                self.stdout.write('\n🔗 Creating hybrid model...')

                # Get Markov instance
                markov_instance = get_markov_instance(
                    n=2,
                    use_word_boundaries=True,
                    corpus_slug=corpus.slug
                )

                # Create hybrid
                hybrid = HybridMarkovLSTM(
                    markov_instance=markov_instance,
                    lstm_model=lstm_model,
                    vocabulary=vocab,
                    base_markov_weight=markov_weight,
                    base_lstm_weight=lstm_weight,
                    confidence_adaptation=True
                )

                # Save hybrid model
                hybrid.save(output_dir)

                self.stdout.write(
                    self.style.SUCCESS(f'✓ Hybrid model saved to {output_dir}')
                )

                # Generate sample words
                self.stdout.write('\n🎲 Sample generations:')
                for i in range(5):
                    word, metadata = hybrid.generate(max_length=10, temperature=1.0)
                    avg_confidence = metadata.get('avg_lstm_confidence', 0)
                    self.stdout.write(
                        f'  {word} (LSTM confidence: {avg_confidence:.2f})'
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error training {corpus.slug}: {str(e)}')
                )
                logger.exception(f'Training failed for {corpus.slug}')
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f'\n\n🎉 Training complete! Models saved to {models_dir}\n'
            )
        )
