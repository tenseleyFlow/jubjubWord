import json
from django.core.management.base import BaseCommand
from django.core import serializers
from django.db import transaction
from jubjub.jubjubword.models import JubJubWord, WordDefinition, WordInteraction


class Command(BaseCommand):
    help = 'Import JubJub data from JSON export'

    def add_arguments(self, parser):
        parser.add_argument(
            'input_file',
            type=str,
            help='Input JSON file path'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before import'
        )

    def handle(self, *args, **options):
        input_file = options['input_file']
        
        # Load data
        with open(input_file, 'r') as f:
            data = json.load(f)
        
        with transaction.atomic():
            if options['clear']:
                self.stdout.write('Clearing existing data...')
                WordInteraction.objects.all().delete()
                WordDefinition.objects.all().delete()
                JubJubWord.objects.all().delete()
            
            # Import in correct order (respecting foreign keys)
            self.stdout.write('Importing JubJub words...')
            for obj in serializers.deserialize('json', json.dumps(data['jubjub_words'])):
                obj.save()
            
            self.stdout.write('Importing word definitions...')
            for obj in serializers.deserialize('json', json.dumps(data['word_definitions'])):
                obj.save()
            
            self.stdout.write('Importing word interactions...')
            for obj in serializers.deserialize('json', json.dumps(data['word_interactions'])):
                obj.save()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully imported data from {input_file}\n'
                f'Words: {JubJubWord.objects.count()}\n'
                f'Definitions: {WordDefinition.objects.count()}\n'
                f'Interactions: {WordInteraction.objects.count()}'
            )
        )