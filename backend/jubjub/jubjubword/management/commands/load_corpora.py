# backend/jubjub/jubjubword/management/commands/load_corpora.py

import os
from django.core.management.base import BaseCommand
from django.conf import settings
from jubjub.jubjubword.models import Corpus


class Command(BaseCommand):
    help = 'Load corpus metadata into the database (actual words stay in files)'

    def handle(self, *args, **options):
        # Define corpus metadata
        corpora_data = [
            {
                'name': 'Classic JubJub',
                'slug': 'classic',
                'description': 'The original JubJub corpus - a delightful mix of Lewis Carroll, Dr. Seuss, and pure nonsense',
                'theme_color': '#3A2449',
                'icon_emoji': '🦜',
                'filename': 'corpus.txt',  # Your existing file
                'is_active': True,
            },
            {
                'name': 'Sci-Fi Technobabble',
                'slug': 'scifi',
                'description': 'Futuristic nonsense perfect for naming your next quantum flux capacitor',
                'theme_color': '#00D4FF',
                'icon_emoji': '🚀',
                'filename': 'scifi.txt',
                'is_active': True,
            },
            {
                'name': 'Fantasy Realm',
                'slug': 'fantasy',
                'description': 'Mystical words for wizards, dragons, and enchanted forests',
                'theme_color': '#8B4513',
                'icon_emoji': '🧙',
                'filename': 'fantasy.txt',
                'is_active': True,
            },
            {
                'name': 'Food Fusion',
                'slug': 'food',
                'description': 'Delicious nonsense for imaginary cuisine',
                'theme_color': '#FF6B6B',
                'icon_emoji': '🍔',
                'filename': 'food.txt',
                'is_active': True,
            },
            {
                'name': 'LinkedIn Buzzword',
                'slug': 'corporate',
                'description': 'Synergistic paradigm shifts for your next meeting',
                'theme_color': '#4A5568',
                'icon_emoji': '💼',
                'filename': 'corporate.txt',
                'is_active': True,
            },
            {
                'name': 'Medical Madness',
                'slug': 'medical',
                'description': 'Sounds like it belongs in a medical journal',
                'theme_color': '#00CED1',
                'icon_emoji': '🔬',
                'filename': 'medical.txt',
                'is_active': True,
            }
        ]
        
        created_count = 0
        updated_count = 0
        missing_files = []
        
        for corpus_data in corpora_data:
            # Check if file exists
            file_path = os.path.join(
                settings.BASE_DIR, 'jubjub', 'jubjubword', corpus_data['filename']
            )
            
            if not os.path.exists(file_path):
                missing_files.append(corpus_data['filename'])
                self.stdout.write(
                    self.style.WARNING(f'⚠️  File not found: {corpus_data["filename"]} for {corpus_data["name"]}')
                )
                continue
            
            corpus, created = Corpus.objects.update_or_create(
                slug=corpus_data['slug'],
                defaults=corpus_data
            )
            
            # Update word count from file
            word_count = corpus.update_word_count()
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created corpus: {corpus.name} ({word_count} words from {corpus.filename})')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'📝 Updated corpus: {corpus.name} ({word_count} words from {corpus.filename})')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully processed {created_count + updated_count} corpora '
                f'({created_count} created, {updated_count} updated)'
            )
        )
        
        if missing_files:
            self.stdout.write(
                self.style.WARNING(
                    f'\n⚠️  Missing files: {", ".join(missing_files)}\n'
                    f'Please create these files in the jubjubword directory.'
                )
            )