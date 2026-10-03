"""
gurobi_license.py -- wartet, bis Gurobi eine Lizenz (ein Token) vergeben
kann, und reserviert sie dabei gleich fuer den restlichen Prozess.

Hintergrund (laut Gurobi-Doku):
  * Ein Client holt sich das Token vom Token-Server, wenn er eine
    Gurobi-Umgebung anlegt, und gibt es beim Zerstoeren der Umgebung
    zurueck.
  * Der Token-Server hat KEINE Warteschlange. Sind alle Tokens vergeben,
    wirft das Anlegen der Umgebung einen gurobipy.GurobiError.
  * Empfohlen ist, es in Abstaenden erneut zu versuchen und den Server
    nicht mit Anfragen zu fluten.

Warum "pruefen" und "reservieren" hier dasselbe sind:
  Eine reine Vorab-Abfrage (z.B. `gurobi_cl --tokens`) waere nur eine
  Momentaufnahme -- zwischen Abfrage und Rechenbeginn kann ein anderer
  Task das letzte Token wegschnappen. Deshalb legen wir hier die
  Default-Umgebung von gurobipy tatsaechlich an. Sie bleibt danach fuer
  den ganzen Prozess bestehen (auch nach model.dispose()) und haelt das
  Token. Jedes spaetere gp.Model() ohne env=... in den Methoden nutzt
  genau diese Umgebung, verbraucht also KEIN zweites Token.

  Wichtig fuer eure Methoden: keine eigenen gp.Env()-Objekte zusaetzlich
  anlegen -- jede Umgebung haelt ein eigenes Token.
"""
from __future__ import annotations

import random
import time

import gurobipy as gp


class LicenseUnavailableError(RuntimeError):
    """Nach Ablauf der maximalen Wartezeit war kein Token zu bekommen."""

    def __init__(self, message: str, waited: float):
        super().__init__(message)
        self.waited = waited


def acquire_license(
    max_wait: float = 900.0,
    poll_interval: float = 60.0,
    jitter: float = 0.25,
) -> float:
    """Legt die Gurobi-Default-Umgebung an und wartet notfalls darauf.

    max_wait       maximale Wartezeit in Sekunden (0 = nur ein Versuch)
    poll_interval  Sekunden zwischen zwei Versuchen
    jitter         zufaellige Streuung des Abstands (+-25 %), damit nicht
                   hunderte wartende Tasks den Server im Gleichtakt abfragen

    Rueckgabe: tatsaechlich gewartete Sekunden (0.0 = sofort bekommen).
    Wirft LicenseUnavailableError, wenn max_wait ueberschritten wird.
    """
    start = time.monotonic()
    attempt = 0

    while True:
        attempt += 1
        try:
            model = gp.Model()  # legt die Default-Umgebung an -> holt das Token
            model.dispose()  # Modell weg, Umgebung (und Token) bleiben
        except gp.GurobiError as exc:
            waited = time.monotonic() - start
            remaining = max_wait - waited
            reason = f"Fehler {exc.errno}: {exc.message}"

            if remaining <= 0:
                raise LicenseUnavailableError(
                    f"Nach {waited:.0f}s und {attempt} Versuch(en) keine Gurobi-Lizenz "
                    f"erhalten. Letzter {reason}",
                    waited,
                ) from exc

            delay = min(poll_interval * random.uniform(1 - jitter, 1 + jitter), remaining)
            print(
                f"[license] Versuch {attempt} fehlgeschlagen ({reason}) -- "
                f"neuer Versuch in {delay:.0f}s (gewartet: {waited:.0f}s von max. {max_wait:.0f}s)",
                flush=True,
            )
            time.sleep(delay)
        else:
            waited = time.monotonic() - start
            if attempt > 1:
                print(
                    f"[license] Lizenz nach {waited:.0f}s ({attempt} Versuchen) erhalten.",
                    flush=True,
                )
            return waited
