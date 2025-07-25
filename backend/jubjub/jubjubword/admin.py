from django.contrib import admin
from django.http import HttpResponse
from django.core import serializers
from django.db.models import Count
import json
from .models import JubJubWord, WordDefinition, WordInteraction, Corpus


def export_as_json(modeladmin, request, queryset):
    response = HttpResponse(content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="{modeladmin.model.__name__}.json"'
    data = serializers.serialize('json', queryset, indent=2)
    response.write(data)
    return response


export_as_json.short_description = 'Export selected as JSON'


@admin.register(Corpus)
class CorpusAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon_emoji', 'word_count', 'times_used', 'is_active', 'created_at')
    list_filter = ('is_active', 'is_premium', 'created_at')
    search_fields = ('name', 'slug', 'description')
    readonly_fields = ('word_count', 'times_used', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'icon_emoji', 'theme_color')
        }),
        ('Corpus Content', {
            'fields': ('words', 'word_count'),
            'classes': ('wide',)
        }),
        ('Settings', {
            'fields': ('is_active', 'is_premium')
        }),
        ('Statistics', {
            'fields': ('times_used', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [export_as_json]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Add generated words count
        qs = qs.annotate(generated_count=Count('generated_words'))
        return qs


@admin.register(JubJubWord)
class JubJubWordAdmin(admin.ModelAdmin):
    list_display = ('word', 'corpus', 'copy_count', 'definition_count', 'first_generated', 'last_shown')
    list_filter = ('corpus', 'first_generated', 'last_shown')
    search_fields = ('word',)
    ordering = ('-copy_count', '-definition_count')
    readonly_fields = ('first_generated', 'last_shown', 'copy_count', 'definition_count')
    
    fieldsets = (
        ('Word Information', {
            'fields': ('word', 'corpus', 'syllables')
        }),
        ('Generation Parameters', {
            'fields': ('temperature', 'markov_order', 'syllable_awareness'),
            'classes': ('collapse',)
        }),
        ('Popularity Metrics', {
            'fields': ('copy_count', 'definition_count', 'first_generated', 'last_shown')
        }),
    )
    
    actions = [export_as_json]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('corpus')


@admin.register(WordDefinition)
class WordDefinitionAdmin(admin.ModelAdmin):
    list_display = ('word', 'definition_preview', 'upvotes', 'downvotes', 'net_votes', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('word__word', 'definition')
    ordering = ('-upvotes', 'created_at')
    readonly_fields = ('upvotes', 'downvotes', 'net_votes', 'created_at')
    
    def definition_preview(self, obj):
        return obj.definition[:50] + '...' if len(obj.definition) > 50 else obj.definition
    definition_preview.short_description = 'Definition'
    
    def net_votes(self, obj):
        return obj.net_votes
    net_votes.short_description = 'Net Votes'
    net_votes.admin_order_field = 'net_votes'
    
    actions = [export_as_json]


@admin.register(WordInteraction)
class WordInteractionAdmin(admin.ModelAdmin):
    list_display = ('word', 'interaction_type', 'session_id_short', 'created_at')
    list_filter = ('interaction_type', 'created_at')
    search_fields = ('word__word', 'session_id')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    def session_id_short(self, obj):
        return obj.session_id[:8] + '...'
    session_id_short.short_description = 'Session ID'
    
    actions = [export_as_json]