import time

from django.core.management.base import BaseCommand

from exams.views_flow import finalize_expired


class Command(BaseCommand):
    help = "Завершает просроченные попытки (чтобы работы не висели «в процессе», если студент закрыл браузер)"

    def add_arguments(self, parser):
        parser.add_argument("--loop", type=int, default=0, help="повторять каждые N секунд (фоновый режим)")

    def handle(self, *args, **opts):
        while True:
            n = finalize_expired()
            if n:
                self.stdout.write(f"Завершено попыток: {n}")
            if not opts["loop"]:
                break
            time.sleep(opts["loop"])
