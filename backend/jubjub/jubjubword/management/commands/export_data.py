import json
from django.core.management.base import BaseCommand
from django.core import serializers
from jubjub.jubjubword.models import JubJubWord, WordDefinition, WordInteraction


class Command(BaseCommand):
    help = 'Export all JubJub data to JSON for migration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='jubjub_data_export.json',
            help='Output file path'
        )

    def handle(self, *args, **options):
        output_file = options['output']
        
        # Collect all data
        data = {
            'jubjub_words': json.loads(
                serializers.serialize('json', JubJubWord.objects.all())
            ),
            'word_definitions': json.loads(
                serializers.serialize('json', WordDefinition.objects.all())
            ),
            'word_interactions': json.loads(
                serializers.serialize('json', WordInteraction.objects.all())
            ),
        }
        
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully exported data to {output_file}\n'
                f'Words: {len(data["jubjub_words"])}\n'
                f'Definitions: {len(data["word_definitions"])}\n'
                f'Interactions: {len(data["word_interactions"])}'
            )
        )