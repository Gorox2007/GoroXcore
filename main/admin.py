from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum
from .models import Club, Tournament, TournamentClub, Match

class TournamentClubInline(admin.TabularInline):
    """Inline для отображения клубов в турнире"""
    model = TournamentClub
    extra = 1
    fields = ['club', 'matches_played', 'wins', 'draws', 'losses', 'goals_for', 'goals_against', 'points_display']
    readonly_fields = ['points_display']
    autocomplete_fields = ['club']
    
    def points_display(self, obj):
        return obj.points
    points_display.short_description = 'Очки'

@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    """Админка для турниров"""
    list_display = [
        'name',
        'country',
        'participants_count',
        'matches_count',
        'logo_preview',
        'actions_column'
    ]
    
    list_filter = ['country']
    search_fields = ['name', 'country']
    list_per_page = 20
    
    # Inline для редактирования клубов прямо в турнире
    inlines = [TournamentClubInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': (
                'name',
                'country',
                'logo'
            )
        }),
        ('Статистика', {
            'fields': ('stats_display',),
            'classes': ('collapse',),
            'description': 'Статистика автоматически рассчитывается'
        })
    )
    
    readonly_fields = ['stats_display']
    
    def participants_count(self, obj):
        """Количество участников"""
        count = obj.clubs.count()
        url = reverse('admin:main_tournamentclub_changelist')
        url += f'?tournament__id__exact={obj.id}'
        return format_html('<a href="{}">{} участников</a>', url, count)
    participants_count.short_description = 'Участники'
    
    def matches_count(self, obj):
        """Количество матчей в турнире"""
        count = obj.matches.count()
        url = reverse('admin:main_match_changelist')
        url += f'?tournament__id__exact={obj.id}'
        return format_html('<a href="{}">{} матчей</a>', url, count)
    matches_count.short_description = 'Матчи'
    
    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: contain; border-radius: 5px;" />', 
                obj.logo.url
            )
        return format_html(
            '<div style="width: 50px; height: 50px; background: #f0f0f0; display: flex; align-items: center; justify-content: center; border-radius: 5px;">'
            '<span style="color: #999;">Нет</span>'
            '</div>'
        )
    logo_preview.short_description = 'Логотип'
    
    def stats_display(self, obj):
        """Отображение статистики турнира"""
        stats = []
        
        # Статистика по участникам
        participants_stats = TournamentClub.objects.filter(tournament=obj).aggregate(
            total_matches=Sum('matches_played'),
            total_wins=Sum('wins'),
            total_draws=Sum('draws'),
            total_losses=Sum('losses'),
            total_goals_for=Sum('goals_for'),
            total_goals_against=Sum('goals_against')
        )
        
        stats.append('<h3>Статистика турнира</h3>')
        stats.append(f'<p><strong>Участников:</strong> {obj.clubs.count()}</p>')
        stats.append(f'<p><strong>Всего матчей:</strong> {participants_stats["total_matches"] or 0}</p>')
        stats.append(f'<p><strong>Побед/Ничьих/Поражений:</strong> {participants_stats["total_wins"] or 0}/{participants_stats["total_draws"] or 0}/{participants_stats["total_losses"] or 0}</p>')
        stats.append(f'<p><strong>Всего голов:</strong> {participants_stats["total_goals_for"] or 0}</p>')
        stats.append(f'<p><strong>Всего пропущено:</strong> {participants_stats["total_goals_against"] or 0}</p>')
        
        
        return mark_safe(''.join(stats))
    stats_display.short_description = 'Статистика'
    
    def actions_column(self, obj):
        """Колонка с действиями"""
        links = []
        
        # Ссылка на просмотр клубов
        clubs_url = reverse('admin:main_tournamentclub_changelist')
        clubs_url += f'?tournament__id__exact={obj.id}'
        links.append(f'<a href="{clubs_url}" style="margin-right: 10px;">👥 Клубы</a>')
        
        # Ссылка на матчи
        matches_url = reverse('admin:main_match_changelist')
        matches_url += f'?tournament__id__exact={obj.id}'
        links.append(f'<a href="{matches_url}">⚽ Матчи</a>')
        
        return format_html(''.join(links))
    actions_column.short_description = 'Действия'


@admin.register(TournamentClub)
class TournamentClubAdmin(admin.ModelAdmin):
    """Админка для участников турниров"""
    list_display = [
        'tournament',
        'club',
        'matches_played',
        'wins',
        'draws',
        'losses',
        'goals_for',
        'goals_against',
        'points_display',
        'goal_difference_display',
        'win_percentage_display'
    ]
    
    list_filter = ['tournament', 'club__country']
    search_fields = ['tournament__name', 'club__name']
    list_select_related = ['tournament', 'club']
    list_per_page = 25
    autocomplete_fields = ['tournament', 'club']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('tournament', 'club')
        }),
        ('Статистика матчей', {
            'fields': (
                'matches_played',
                ('wins', 'draws', 'losses')
            )
        }),
        ('Голы', {
            'fields': ('goals_for', 'goals_against')
        }),
        ('Расчетные показатели', {
            'fields': ('points_display', 'goal_difference_display', 'win_percentage_display'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ['points_display', 'goal_difference_display', 'win_percentage_display']
    
    def points_display(self, obj):
        """Отображение очков"""
        return format_html(
            '<span style="font-weight: bold; color: #2c3e50; font-size: 14px;">{}</span>',
            obj.points
        )
    points_display.short_description = 'Очки'
    
    def goal_difference_display(self, obj):
        """Отображение разницы мячей"""
        gd = obj.goal_difference
        color = '#27ae60' if gd > 0 else ('#e74c3c' if gd < 0 else '#f39c12')
        # Исправлено: форматируем число перед передачей
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, f"{gd:+d}"
        )
    goal_difference_display.short_description = 'Разница'
    
    def win_percentage_display(self, obj):
        """Отображение процента побед"""
        wp = obj.win_percentage
        color = '#27ae60' if wp > 50 else ('#e74c3c' if wp < 30 else '#f39c12')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, wp
        )
    win_percentage_display.short_description = 'Победы %'
    
    def get_queryset(self, request):
        """Оптимизация запроса"""
        queryset = super().get_queryset(request)
        return queryset.select_related('tournament', 'club')
    
    # Действия для массового обновления
    actions = ['recalculate_statistics', 'reset_statistics']
    
    def recalculate_statistics(self, request, queryset):
        """Пересчитать статистику на основе матчей"""
        for tournament_club in queryset:
            # Здесь можно добавить логику пересчета из матчей
            pass
        self.message_user(request, f"Статистика пересчитана для {queryset.count()} записей")
    recalculate_statistics.short_description = "Пересчитать статистику"
    
    def reset_statistics(self, request, queryset):
        """Сбросить статистику"""
        updated = queryset.update(
            matches_played=0,
            wins=0,
            draws=0,
            losses=0,
            goals_for=0,
            goals_against=0
        )
        self.message_user(request, f"Статистика сброшена для {updated} записей")
    reset_statistics.short_description = "Сбросить статистику"


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    """Админка для клубов"""
    list_display = [
        'name',
        'country',
        'town',
        'tournaments_count',
        'matches_count',
        'emblem_preview'
    ]
    
    list_filter = ['country']
    search_fields = ['name', 'country', 'town']
    list_per_page = 25
    
    fieldsets = (
        ('Основная информация', {
            'fields': (
                'name',
                'country',
                'town',
                'founded',
                'stadium',
                'price'
            )
        }),
        ('Статистика', {
            'fields': (
                'goals',
                'goals_missed',
                'possession'
            )
        }),
        ('Последние матчи', {
            'fields': (
                ('match_1', 'match_2', 'match_3', 'match_4', 'match_5'),
                'next_match'
            ),
            'classes': ('collapse',)
        }),
        ('Медиа', {
            'fields': ('emblem',)
        })
    )
    
    def tournaments_count(self, obj):
        """Количество турниров клуба"""
        count = obj.tournament_participations.count()
        url = reverse('admin:main_tournamentclub_changelist')
        url += f'?club__id__exact={obj.id}'
        return format_html('<a href="{}">{} турниров</a>', url, count)
    tournaments_count.short_description = 'Турниры'
    
    def matches_count(self, obj):
        """Количество матчей клуба"""
        home = obj.home_matches.count()
        away = obj.away_matches.count()
        total = home + away
        return f"{total} ({home} дома, {away} в гостях)"
    matches_count.short_description = 'Матчи'
    
    def emblem_preview(self, obj):
        if obj.emblem:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: contain; border-radius: 50%; border: 2px solid #ddd;" />', 
                obj.emblem.url
            )
        return format_html(
            '<div style="width: 50px; height: 50px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); '
            'display: flex; align-items: center; justify-content: center; border-radius: 50%; border: 2px solid #ddd;">'
            '<span style="color: white; font-weight: bold; font-size: 18px;">{}</span>'
            '</div>',
            obj.name[:2].upper()
        )
    emblem_preview.short_description = 'Эмблема'


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    """Админка для матчей"""
    list_display = [
        'home_club',
        'away_club',
        'datetime',
        'status_badge',
        'tournament_display',
        'score_display'
    ]
    
    list_filter = ['status', 'datetime', 'tournament']
    search_fields = [
        'home_club__name',
        'away_club__name',
        'tournament__name',
        'town',
        'stadium'
    ]
    list_select_related = ['home_club', 'away_club', 'tournament']
    autocomplete_fields = ['home_club', 'away_club', 'tournament']
    date_hierarchy = 'datetime'
    list_per_page = 30
    
    fieldsets = (
        ('Основная информация', {
            'fields': (
                'home_club',
                'away_club',
                'tournament',
                'datetime',
                'status',
                'town',
                'stadium'
            )
        }),
        ('Результат матча', {
            'fields': (
                'home_goals',
                'away_goals'
            )
        }),
        ('Статистика владения и ударов', {
            'fields': (
                ('home_possession', 'away_possession'),
                ('home_shots', 'away_shots'),
                ('home_shots_on_target', 'away_shots_on_target')
            )
        }),
        ('Дополнительная статистика', {
            'fields': (
                ('home_red_cards', 'away_red_cards'),
                ('home_saves', 'away_saves')
            ),
            'classes': ('collapse',)
        })
    )
    
    def status_badge(self, obj):
        """Отображение статуса с цветным бейджем"""
        colors = {
            'scheduled': '#3498db',  # синий
            'finished': '#2ecc71',    # зеленый
        }
        color = colors.get(obj.status, '#95a5a6')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Статус'
    status_badge.admin_order_field = 'status'
    
    def score_display(self, obj):
        """Отображение счета матча"""
        if obj.status == 'finished':
            home_color = '#27ae60' if obj.home_goals > obj.away_goals else ('#e74c3c' if obj.home_goals < obj.away_goals else '#f39c12')
            away_color = '#27ae60' if obj.away_goals > obj.home_goals else ('#e74c3c' if obj.away_goals < obj.home_goals else '#f39c12')
            
            return format_html(
                '<div style="display: flex; align-items: center; gap: 5px;">'
                '<span style="color: {}; font-weight: bold; font-size: 14px;">{}</span>'
                '<span>:</span>'
                '<span style="color: {}; font-weight: bold; font-size: 14px;">{}</span>'
                '</div>',
                home_color, obj.home_goals, away_color, obj.away_goals
            )
        return "—"
    score_display.short_description = 'Счет'
    
    def tournament_display(self, obj):
        """Отображение турнира со ссылкой"""
        if obj.tournament:
            url = reverse('admin:main_tournament_change', args=[obj.tournament.id])
            return format_html('<a href="{}">{}</a>', url, obj.tournament.name)
        return "—"
    tournament_display.short_description = 'Турнир'
    
    actions = ['mark_as_finished', 'mark_as_scheduled']
    
    def mark_as_finished(self, request, queryset):
        """Пометить как завершенные"""
        updated = queryset.update(status='finished')
        self.message_user(request, f"{updated} матчей помечены как завершенные")
    mark_as_finished.short_description = "Пометить как завершенные"
    
    def mark_as_scheduled(self, request, queryset):
        """Пометить как запланированные"""
        updated = queryset.update(status='scheduled')
        self.message_user(request, f"{updated} матчей помечены как запланированные")
    mark_as_scheduled.short_description = "Пометить как запланированные"
    
    def get_queryset(self, request):
        """Оптимизация запроса"""
        queryset = super().get_queryset(request)
        return queryset.select_related('home_club', 'away_club', 'tournament')