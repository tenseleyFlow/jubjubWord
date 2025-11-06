"""
Management command to prebuild all Markov models for faster cold starts.

Usage:
    python manage.py prebuild_markov_models
    python manage.py prebuild_markov_models --corpus scifi
    python manage.py prebuild_markov_models --prune 0.01
"""

from django.core.management.base import BaseCommand
from jubjub.jubjubword.models import Corpus
from jubjub.jubjubword.markov import get_markov_instance, clear_corpus_cache
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Prebuild Markov models for all or specific corpora'

    def add_arguments(self, parser):
        parser.add_argument(
            '--corpus',
            type=str,
            help='Specific corpus slug to build (default: all active corpora)',
        )
        parser.add_argument(
            '--prune',
            type=float,
            default=0.0,
            help='Prune threshold for rare transitions (0.0-1.0, default: 0.0 = no pruning)',
        )
        parser.add_argument(
            '--orders',
            type=str,
            default='2',
            help='Comma-separated Markov orders to build (default: 2)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force rebuild even if models exist',
        )

    def handle(self, *args, **options):
        corpus_slug = options.get('corpus')
        prune_threshold = options.get('prune')
        orders = [int(n.strip()) for n in options.get('orders').split(',')]
        force = options.get('force')

        if force:
            self.stdout.write(self.style.WARNING('Clearing existing caches...'))
            clear_corpus_cache()

        # Get corpora to build
        if corpus_slug:
            try:
                corpora = [Corpus.objects.get(slug=corpus_slug, is_active=True)]
            except Corpus.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Corpus "{corpus_slug}" not found'))
                return
        else:
            corpora = Corpus.objects.filter(is_active=True)

        total_corpora = len(corpora)
        total_models = total_corpora * len(orders) * 2  # 2 for use_word_boundaries True/False

        self.stdout.write(
            self.style.SUCCESS(
                f'Building {total_models} models for {total_corpora} corpora...'
            )
        )

        built_count = 0
        total_size_kb = 0

        for corpus in corpora:
            self.stdout.write(f'\n{corpus.name} ({corpus.slug}):')

            for n in orders:
                for use_boundaries in [True, False]:
                    boundary_str = 'with' if use_boundaries else 'without'
                    self.stdout.write(
                        f'  Building n={n}, {boundary_str} boundaries...',
                        ending=''
                    )

                    try:
                        # Get or create the instance (this will save to disk)
                        instance = get_markov_instance(
                            n=n,
                            use_word_boundaries=use_boundaries,
                            corpus_slug=corpus.slug
                        )

                        # Apply pruning if requested
                        if prune_threshold > 0:
                            removed = instance.prune_rare_transitions(prune_threshold)
                            self.stdout.write(
                                self.style.WARNING(f' pruned {removed} transitions'),
                                ending=''
                            )

                        # Get statistics
                        stats = instance.get_statistics()
                        total_size_kb += stats.get('estimated_memory_kb', 0)

                        self.stdout.write(
                            self.style.SUCCESS(
                                f' ✓ ({stats["num_states"]} states, '
                                f'{stats["estimated_memory_kb"]:.1f} KB, '
                                f'{stats["training_time_seconds"]:.3f}s)'
                            )
                        )

                        built_count += 1

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f' ✗ Error: {str(e)}'))
                        logger.exception(f'Failed to build model for {corpus.slug}')

        self.stdout.write(
            self.style.SUCCESS(
                f'\n\nBuilt {built_count}/{total_models} models successfully'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Total estimated memory: {total_size_kb:.1f} KB ({total_size_kb / 1024:.2f} MB)'
            )
        )
