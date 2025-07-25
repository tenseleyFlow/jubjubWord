# backend/jubjub/jubjubword/management/commands/reset_sequences.py

from django.core.management.base import BaseCommand
from django.db import connection
from django.apps import apps


class Command(BaseCommand):
    help = 'Reset PostgreSQL sequences for all models'

    def handle(self, *args, **options):
        self.stdout.write('Resetting PostgreSQL sequences...')
        
        with connection.cursor() as cursor:
            # Get all models from our app
            app_models = apps.get_app_config('jubjubword').get_models()
            
            for model in app_models:
                table_name = model._meta.db_table
                
                try:
                    # Check if table exists and has an id field
                    cursor.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = %s AND column_name = 'id'",
                        [table_name]
                    )
                    
                    if cursor.fetchone():
                        # Get max ID
                        cursor.execute(f"SELECT MAX(id) FROM {table_name}")
                        max_id = cursor.fetchone()[0]
                        
                        if max_id is not None:
                            # Reset sequence
                            sequence_name = f"{table_name}_id_seq"
                            cursor.execute(
                                f"SELECT setval('{sequence_name}', %s, true)",
                                [max_id]
                            )
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✅ Reset {table_name} sequence to {max_id + 1}'
                                )
                            )
                        else:
                            self.stdout.write(
                                self.style.WARNING(f'⚠️  No data in {table_name}')
                            )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Error with {table_name}: {e}')
                    )
        
        self.stdout.write(
            self.style.SUCCESS('\nSequences reset successfully!')
        )