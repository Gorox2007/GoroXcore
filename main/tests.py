from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Club, Match, Tournament, TournamentClub


class MonolithApiTests(TestCase):
    def setUp(self):
        self.home = Club.objects.create(
            name="Barcelona",
            country="Spain",
            town="Barcelona",
            price=1_000_000,
            founded=1899,
            stadium="Camp Nou",
        )
        self.away = Club.objects.create(
            name="Real Madrid",
            country="Spain",
            town="Madrid",
            price=1_000_000,
            founded=1902,
            stadium="Santiago Bernabeu",
        )
        self.tournament = Tournament.objects.create(name="La Liga", country="Spain")
        self.match = Match.objects.create(
            home_club=self.home,
            away_club=self.away,
            tournament=self.tournament,
            town="Barcelona",
            stadium="Camp Nou",
            datetime=timezone.now(),
            seats_available=250,
            price=Decimal("1500.00"),
            status="scheduled",
        )

    def test_match_ticketing_info_endpoint(self):
        response = self.client.get(
            reverse("match_ticketing_info", kwargs={"match_id": self.match.id})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["match_id"], self.match.id)
        self.assertEqual(payload["home_club"], "Barcelona")
        self.assertEqual(payload["away_club"], "Real Madrid")
        self.assertEqual(payload["seats_available"], 250)
        self.assertEqual(payload["price"], "1500.00")
        self.assertEqual(payload["currency"], "RUB")

    def test_model_properties(self):
        participant = TournamentClub.objects.create(
            tournament=self.tournament,
            club=self.home,
            matches_played=3,
            wins=2,
            draws=1,
            losses=0,
            goals_for=7,
            goals_against=3,
        )

        self.assertEqual(participant.points, 7)
        self.assertEqual(participant.goal_difference, 4)
        self.assertEqual(participant.win_percentage, 66.7)
        self.assertEqual(self.tournament.participants_count, 1)

    def test_metrics_endpoint(self):
        self.client.get("/")
        response = self.client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("gx_http_requests_total", body)
        self.assertIn("gx_http_request_duration_seconds", body)
