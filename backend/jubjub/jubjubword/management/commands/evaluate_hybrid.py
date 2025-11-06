"""
Evaluate and compare hybrid models vs pure Markov

Usage:
    python manage.py evaluate_hybrid --corpus scifi
    python manage.py evaluate_hybrid --corpus scifi --samples 200
"""

from django.core.management.base import BaseCommand
from jubjub.jubjubword.models import Corpus
from jubjub.jubjubword.markov import get_markov_instance
from jubjub.jubjubword.hybrid import HybridMarkovLSTM
from jubjub.jubjubword.hybrid_evaluation import (
    compare_generation_methods,
    analyze_hybrid_contributions,
    print_comparison_report,
    print_contribution_analysis
)
from pathlib import Path
from django.conf import settings


class Command(BaseCommand):
    help = 'Evaluate hybrid models and compare with pure Markov'

    def add_arguments(self, parser):
        parser.add_argument(
            '--corpus',
            type=str,
            required=True,
            help='Corpus slug to evaluate (e.g., scifi)',
        )
        parser.add_argument(
            '--samples',
            type=int,
            default=100,
            help='Number of words to generate for comparison (default: 100)',
        )
        parser.add_argument(
            '--temperature',
            type=float,
            default=1.0,
            help='Generation temperature (default: 1.0)',
        )
        parser.add_argument(
            '--max-length',
            type=int,
            default=10,
            help='Maximum word length (default: 10)',
        )

    def handle(self, *args, **options):
        corpus_slug = options.get('corpus')
        num_samples = options.get('samples')
        temperature = options.get('temperature')
        max_length = options.get('max_length')

        # Load corpus
        try:
            corpus = Corpus.objects.get(slug=corpus_slug, is_active=True)
        except Corpus.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Corpus "{corpus_slug}" not found'))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'\n🔬 Evaluating: {corpus.name} ({corpus.slug})\n'
            )
        )

        # Load Markov model
        self.stdout.write('Loading Markov model...')
        markov_instance = get_markov_instance(
            n=2,
            use_word_boundaries=True,
            corpus_slug=corpus.slug
        )

        # Load hybrid model
        models_dir = Path(settings.BASE_DIR) / 'jubjub' / 'jubjubword' / 'hybrid_models'
        hybrid_dir = models_dir / corpus.slug

        if not hybrid_dir.exists():
            self.stdout.write(
                self.style.ERROR(
                    f'\n✗ Hybrid model not found at {hybrid_dir}\n'
                    f'  Run: python manage.py train_hybrid_models --corpus {corpus_slug}\n'
                )
            )
            return

        self.stdout.write('Loading hybrid model...')
        try:
            hybrid_model = HybridMarkovLSTM.load(hybrid_dir, markov_instance)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Failed to load hybrid model: {str(e)}')
            )
            return

        self.stdout.write(self.style.SUCCESS('✓ Models loaded\n'))

        # Run comparison
        self.stdout.write(f'Generating {num_samples} words with each method...')

        comparison = compare_generation_methods(
            markov_instance=markov_instance,
            hybrid_model=hybrid_model,
            num_samples=num_samples,
            temperature=temperature,
            max_length=max_length
        )

        # Print comparison report
        print_comparison_report(comparison, corpus_name=corpus.name)

        # Analyze hybrid contributions
        self.stdout.write('\nAnalyzing hybrid model contributions...')

        contribution_analysis = analyze_hybrid_contributions(
            hybrid_model=hybrid_model,
            num_samples=20,
            max_length=max_length
        )

        print_contribution_analysis(contribution_analysis)

        # Interpretation
        hybrid_stats = comparison['hybrid']
        markov_stats = comparison['markov']

        print("\n" + "="*70)
        print("  Interpretation")
        print("="*70 + "\n")

        pronounce_diff = hybrid_stats['avg_pronounceability'] - markov_stats['avg_pronounceability']
        if pronounce_diff > 0.05:
            print(f"✓ Hybrid model produces MORE pronounceable words (+{pronounce_diff:.2f})")
            print(f"  The LSTM learned phonotactic patterns!")
        elif pronounce_diff < -0.05:
            print(f"✗ Hybrid model produces LESS pronounceable words ({pronounce_diff:.2f})")
            print(f"  May need more training or different hyperparameters")
        else:
            print(f"≈ Similar pronounceability ({pronounce_diff:+.2f})")
            print(f"  Models perform comparably")

        diversity_diff = hybrid_stats['unique_ratio'] - markov_stats['unique_ratio']
        if diversity_diff > 0.05:
            print(f"\n✓ Hybrid model has MORE diversity (+{diversity_diff:.2%})")
            print(f"  LSTM adds creative variation")
        elif diversity_diff < -0.05:
            print(f"\n✗ Hybrid model has LESS diversity ({diversity_diff:.2%})")
            print(f"  May be overfitting")
        else:
            print(f"\n≈ Similar diversity ({diversity_diff:+.2%})")

        print("\n" + "="*70 + "\n")
