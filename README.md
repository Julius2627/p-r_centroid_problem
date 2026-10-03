# Gurobi-Batchläufe auf dem bwUniCluster 3.0

Löst viele Instanzen (CSV-Dateien) mit mehreren Lösungsmethoden
(Python-Dateien in `methods/`) parallel über einen Slurm-Array-Job und
fasst am Ende alles automatisch in **einer** Ergebnis-CSV zusammen.
Jede Kombination aus Instanz und Methode ist ein eigener, kurzer Job.

**Der Alltag in vier Schritten:** `git pull` → `./submit_all.sh` →
warten → `results/final_results.csv` abholen.

## Inhalt

1. [Ordnerstruktur](#ordnerstruktur)
2. [Wie die Arbeit aufgeteilt wird](#wie-die-arbeit-aufgeteilt-wird)
3. [Einmaliges Setup](#einmaliges-setup)
4. [Regulärer Workflow](#regulärer-workflow)
5. [Erster Lauf: worauf du achten solltest](#erster-lauf-worauf-du-achten-solltest)
6. [Ergebnisdateien](#ergebnisdateien)
7. [Zeit, Ressourcen und Parallelität](#zeit-ressourcen-und-parallelität)
8. [Gurobi-Lizenz](#gurobi-lizenz)
9. [Environment: gesperrte Versionen](#environment-gesperrte-versionen)
10. [Fehlersuche und Nachrechnen](#fehlersuche-und-nachrechnen)
11. [Neue Lösungsmethode hinzufügen](#neue-lösungsmethode-hinzufügen)

## Ordnerstruktur

```
gurobi_hpc_workflow/
├── README.md
├── requirements.txt        # exakt gesperrte Paketversionen
├── config.sh               # zentrale Einstellungen -- hier EINMAL anpassen
├── setup_env.sh            # einmalig: venv + gesperrte Pakete installieren
├── submit_all.sh           # NORMALER WORKFLOW: hier startest du alles
├── solve_array.sh          # Slurm-Array-Job (1 Task = 1 Instanz-Methode-Paar)
├── merge_results.sh        # Slurm-Job, fasst Ergebnisse zusammen
├── main.py                 # führt GENAU EINE Instanz-Methode-Kombination aus
├── grid.py                 # gemeinsame Logik: Instanz/Methode-Aufteilung
├── gurobi_license.py       # reserviert vor dem Rechnen ein Token, wartet notfalls
├── collect_results.py      # führt alle Teil-Ergebnisse zu 1 CSV zusammen
├── check_license.py        # prüft, ob Gurobi eine echte Lizenz findet
├── test_license.sh         # OPTIONAL: Lizenz-Test auf einem Rechenknoten
├── methods/
│   ├── __init__.py
│   └── _TEMPLATE_method.py # Vorlage (Unterstrich = wird NICHT mitgezählt)
├── instances/              # deine Instanz-CSVs (einfach reinlegen)
├── results/
│   ├── partial/            # 1 CSV pro (Instanz, Methode)-Paar
│   └── final_results.csv   # <- DAS Ergebnis, das du am Ende abholst
└── logs/                   # Slurm-Logs
```

## Wie die Arbeit aufgeteilt wird

`main.py` läuft **nie** über mehrere Instanzen oder Methoden in einer
Schleife -- das würde Tage dauern und dich auf einem einzigen
Rechenknoten blockieren. Stattdessen bearbeitet jeder Aufruf **genau
eine** (Instanz, Methode)-Kombination:

```bash
python main.py --task-id <N> --instance-dir instances
```

`<N>` ist die Slurm-Array-Task-ID. `grid.py` rechnet daraus zurück, welche
Instanz und welche Methode gemeint sind:

```
instance_idx, model_idx = divmod(N, anzahl_methoden)
```

Bei z. B. 50 Instanzen × 6 Methoden entstehen 300 unabhängige Tasks, die
Slurm parallel einplant (begrenzt durch `MAX_CONCURRENT` und die
Cluster-Auslastung). Die Gesamtlaufzeit sinkt dadurch von "Summe aller
Einzelläufe" auf ungefähr "Laufzeit des langsamsten Einzellaufs".

**Was ein Task der Reihe nach macht:**

1. `config.sh` laden, Python- und Gurobi-Modul laden, venv aktivieren
2. Ein Gurobi-Lizenz-Token reservieren, notfalls darauf warten
3. Die Methode auf der Instanz ausführen (`solve()` aus `methods/`)
4. Genau eine Ergebnisdatei `results/partial/<instanz>__<methode>.csv`
   schreiben

**Warum das robust ist:**

- **Kein gemeinsames Schreiben in eine Datei.** Jeder Task schreibt nur
  seine eigene Datei, erst der Merge-Job führt alles zusammen -- so gibt
  es keine Race Conditions.
- **Der Merge-Job hängt automatisch am Array-Job**
  (`--dependency=afterany:<jobid>`) und startet, sobald alle Tasks
  beendet sind, egal ob erfolgreich oder nicht.
- **Instanzen und Methoden werden automatisch erkannt** (Verzeichnis-Scan
  in `grid.py`, alphabetisch sortiert). Neue Instanz-CSV in `instances/`
  oder neue Methode in `methods/` sind beim nächsten `submit_all.sh` dabei.

**Task-IDs sind nur stabil, solange sich `instances/` und `methods/`
nicht ändern.** Fügst du zwischen einem Lauf und einem Nachlauf eine
Instanz oder Methode hinzu, verschieben sich die IDs (siehe
[Nachrechnen](#nachrechnen-einzelner-tasks)).

Zum Testen kannst du mehrere Methoden am Stück auf einer Instanz laufen
lassen (z. B. lokal):

```bash
python main.py instances/beispiel.csv --models methodeA methodeB
```

## Einmaliges Setup

```bash
ssh ka_ab1234@uc3.scc.kit.edu          # dein Präfix/Username

ws_allocate gurobi_ws 60               # Workspace anlegen (60 Tage, anpassen)
cd $(ws_find gurobi_ws)
git clone <DEIN_GITHUB_REPO_URL> repo
cd repo

bash setup_env.sh                      # venv + gesperrte Pakete installieren
```

Danach einmal `config.sh` durchgehen (alle `TODO`s: Workspace-Name,
Modulnamen), und in `solve_array.sh` sowie `merge_results.sh` die
`--mail-user=`-Zeile ausfüllen. Ab dann bleibt das stehen.

`setup_env.sh` installiert erst alle Pakete und prüft **am Ende** die
Gurobi-Lizenz (`check_license.py`). Schlägt nur dieser Test fehl, ist die
venv trotzdem fertig -- siehe [Gurobi-Lizenz](#gurobi-lizenz).

> **Workspaces laufen ab.** Kopiere `final_results.csv` nach jedem Lauf
> auf deinen Mac und verlängere den Workspace rechtzeitig (`ws_extend`).

## Regulärer Workflow

1. Lokal: Instanz-CSVs und Methoden-Dateien aktualisieren, nach GitHub
   pushen.
2. Auf dem Cluster: `git pull`
3. **Vor einem neuen Lauf aufräumen** (siehe Hinweis unten), dann:
   `./submit_all.sh` -- das ist der einzige Befehl, der pro Lauf nötig ist.
4. Warten. Fortschritt mit `squeue -u $USER`; optional per Mail über
   `--mail-user` in den Slurm-Skripten.
5. Vom Mac abholen:
   ```bash
   scp ka_ab1234@uc3.scc.kit.edu:$(ws_find gurobi_ws)/repo/results/final_results.csv .
   ```

Optional: die maximale Anzahl gleichzeitig laufender Tasks mitgeben
(Default 5, siehe [Parallelität](#wie-viele-jobs-gleichzeitig)):

```bash
./submit_all.sh 40
```

**Aufräumen vor einem neuen Lauf:** `submit_all.sh` rechnet immer das
**komplette** Raster neu und überspringt nichts. Der Merge-Job nimmt alle
Dateien in `results/partial/` -- auch übrig gebliebene aus früheren
Läufen, die es im aktuellen Raster gar nicht mehr gibt. Deshalb vorher:

```bash
# final_results.csv vorher sichern, sie wird beim nächsten Merge überschrieben
rm results/partial/*.csv
```

## Erster Lauf: worauf du achten solltest

`config.sh` wird in **jedem** Slurm-Job geladen und ruft dabei `ws_find`
auf. Ob das auf Rechenknoten funktioniert, ist hier nicht geprüft. Starte
deshalb klein und schau in das erste Log, bevor du hochskalierst:

1. `./submit_all.sh 5` (nur 5 Tasks gleichzeitig)
2. Nach ein bis zwei Minuten `squeue -u $USER`, dann Task 0 ansehen:
   ```bash
   cat logs/gurobi_solve_<ARRAY_JOBID>_0.out
   cat logs/gurobi_solve_<ARRAY_JOBID>_0.err
   ```
3. Erwartet wird: keine Fehlermeldung von `ws_find` oder `module`, die
   Zeile `[license] Lizenz sofort verfuegbar.` und am Ende
   `1 Ergebniszeile(n) geschrieben nach results/partial/...`.
4. Während der Läufe `gurobi_cl --tokens` ausführen: `current` sollte
   ungefähr der Zahl laufender Tasks entsprechen.
5. Erst wenn das stimmt, mit `./submit_all.sh <n>` hochskalieren.

Schlagen Tasks sofort fehl, sind die häufigsten Ursachen: `ws_find` auf
Rechenknoten nicht verfügbar (dann `WSROOT` in `config.sh` fest
eintragen), falsche Modulnamen oder eine fehlende venv.

Alternativ prüft `sbatch test_license.sh` (optional) auf einem
Rechenknoten den Token-Server; die Ausgabe steht in
`logs/license_test_<jobid>.out`.

## Ergebnisdateien

`results/final_results.csv` hat pro (Instanz, Methode) eine Zeile:

| Spalte | Bedeutung |
|---|---|
| `instance` | Instanz-Dateiname ohne `.csv` |
| `model` | Methodenname (Dateiname in `methods/` ohne `.py`) |
| `status` | siehe unten |
| `objective` | beste gefundene Lösung; leer, wenn keine gefunden wurde |
| `bound` | beste bewiesene Schranke |
| `gap` | MIP-Gap; leer, wenn keine Lösung gefunden wurde |
| `runtime_sec` | Gurobi-Laufzeit (`model.Runtime`) |
| `wall_time_sec` | Gesamtdauer von `solve()` inkl. Einlesen, Precalculation und Modellaufbau (ohne Lizenz-Wartezeit) |
| `license_wait_sec` | Wartezeit auf ein Lizenz-Token |
| `error` | Fehlertext bei `ERROR` bzw. `NO_LICENSE` |

**`status`:** Die Werte `OPTIMAL`, `TIME_LIMIT`, `INFEASIBLE`,
`INTERRUPTED`, `SUBOPTIMAL` (bei anderen Gurobi-Zuständen der Zahlencode)
kommen aus deiner Methode -- so setzt es `_TEMPLATE_method.py`. Zwei
Werte setzt `main.py` selbst:

- `ERROR`: Deine Methode hat eine Ausnahme geworfen. Die anderen Tasks
  sind davon nicht betroffen; der Traceback steht in der `.err`-Datei.
- `NO_LICENSE`: Bis zum Ablauf der Wartezeit war kein Token zu bekommen.

Ein Slurm-Task, dessen Methode `ERROR` meldet, endet trotzdem mit Exit-Code
0 (also `COMPLETED`). Fehlgeschlagene Rechnungen findest du deshalb am
besten in der CSV:

```bash
grep -E ',(ERROR|NO_LICENSE),' results/final_results.csv
```

Zusätzliche Spalten brauchen einen Eintrag in `RESULT_FIELDS` in `main.py`,
sonst werden sie ignoriert. Am Ende des Merge-Laufs steht im Log
(`logs/merge_results_<jobid>.out`), ob Kombinationen **gar keine**
Ergebnisdatei geliefert haben (z. B. wegen Walltime-Kill).

## Zeit, Ressourcen und Parallelität

### Was `--time` bedeutet

`#SBATCH --time=...` ist nur eine **Obergrenze**. Der Job endet, sobald das
Skript fertig ist -- rechnet ein Task nur 45 Minuten, obwohl 2 Stunden
erlaubt sind, wird er nach 45 Minuten beendet und die Kerne sind sofort
wieder frei. Überschreitet er die Grenze, beendet Slurm ihn hart, dann
wird **kein** Ergebnis mehr geschrieben. Auch `--time-limit` (Gurobi) ist
nur eine Obergrenze: Findet Gurobi das Optimum früher, endet der Task
früher.

### Zeitbudget pro Task

Die Lizenz-Wartezeit zählt zur Slurm-Walltime, weil der Task währenddessen
schon läuft:

```
--license-wait (max. 900 s) + --time-limit (5400 s) = 6300 s  ≈ 1h45
```

Das passt in `--time=02:00:00` und lässt 15 Minuten Reserve für Einlesen
und Precalculation. Gurobis eigenes Zeitlimit muss **kürzer** sein als die
Slurm-Walltime, damit Gurobi noch sauber ein (Teil-)Ergebnis schreiben
kann, bevor Slurm den Job beendet. Änderst du eine der Zahlen, passe
`--time` in `solve_array.sh` mit an. `--mem` und `--cpus-per-task` sind
Startwerte; `--cpus-per-task` sollte zum `Threads`-Parameter in deiner
Methode passen.

### Wie viele Jobs gleichzeitig?

Es gibt zwei getrennte Grenzen:

1. **Lizenz-Tokens.** Gurobi holt sich (in der Regel) pro laufendem Prozess
   ein Token vom Token-Server; die Kapazität wird mit anderen Nutzern
   geteilt. Aktuellen Stand zeigt
   `module load "$GUROBI_MODULE" && gurobi_cl --tokens` (bei euch zuletzt:
   maximal 4096 gleichzeitige Nutzungen). Ist kein Token frei, wartet ein
   Task (siehe [Gurobi-Lizenz](#gurobi-lizenz)), statt sofort zu scheitern.
2. **Cluster.** Laut Wiki höchstens 1920 CPU-Kerne gleichzeitig pro Nutzer;
   bei `--cpus-per-task=4` rechnerisch 480 Tasks.

Vorgehen: mit dem Default `./submit_all.sh` (5 gleichzeitig) starten, im
Lauf `gurobi_cl --tokens` prüfen (so siehst du, wie viele Tokens deine Tasks
wirklich belegen) und erst dann mit `./submit_all.sh <n>` erhöhen. Halte
`n` deutlich unter den freien Tokens, weil andere Nutzer dieselben Tokens
brauchen.

Bei sehr vielen Kombinationen (mehrere Tausend Tasks) kann es ein Limit für
die Array-Größe geben (`MaxArraySize`, clusterabhängig). Prüfen mit
`scontrol show config | grep MaxArraySize`, oder beim bwHPC-Support
nachfragen, falls `submit_all.sh` mit einem Slurm-Fehler abbricht.

## Gurobi-Lizenz

Auf der bwUniCluster 3.0 setzt das Gurobi-Modul `GRB_LICENSE_FILE` selbst
auf eine zentrale Client-Lizenz (`gurobi_client.lic`), die auf einen
**Token-Server** verweist. Die Verbindung passiert automatisch, sobald
Gurobi die erste Umgebung anlegt (`gp.Model()`). Du brauchst nur
`module load "$GUROBI_MODULE"` in jedem Job (steht in `solve_array.sh`) und
darfst `GRB_LICENSE_FILE` **nicht selbst überschreiben**.

`gurobipy` selbst kommt komplett aus `pip` (das PyPI-Wheel enthält die
Gurobi-Bibliothek); ein manuelles `PYTHONPATH` ist nicht nötig. Das
Python-Paket bringt aber **keine Lizenz** mit.

**Ohne gültige Lizenz** fällt Gurobi still auf eine größenbeschränkte
"Restricted license" zurück (Meldung beim Start: `Restricted license - for
non-production use only`). Dann laufen nur winzige Modelle, größere
brechen mit `GurobiError 10010` ab. `check_license.py` prüft das mit einem
3000-Variablen-Modell; `setup_env.sh` ruft es am Ende auf.

Diagnose, falls der Test fehlschlägt (vorher `source config.sh`):

```bash
module load "$GUROBI_MODULE"
module show "$GUROBI_MODULE"      # setzt das Modul GRB_LICENSE_FILE / einen Token-Server?
gurobi_cl --license               # zeigt die gefundene Lizenzdatei
gurobi_cl --tokens                # Status und Kapazität des Token-Servers
```

Ob und wie deine Einrichtung Gurobi zentral lizenziert, erfährst du beim
bwHPC-Support (bw-support.scc.kit.edu).

### Warten auf ein freies Token

Bevor `main.py` eine Methode rechnet, reserviert es ein Token
(`gurobi_license.py`). Der Token-Server hat laut Gurobi **keine
Warteschlange**: Sind alle Tokens vergeben, wirft das Anlegen der
Gurobi-Umgebung einen Fehler. Deshalb versucht jeder Task es in Abständen
erneut. Die Optionen von `main.py` (in `solve_array.sh` fest eingetragen):

| Option | Default | Bedeutung |
|---|---|---|
| `--license-wait` | 900 | maximale Wartezeit in Sekunden; `0` = nur ein Versuch |
| `--license-poll` | 60 | Sekunden zwischen zwei Versuchen (±25 % Streuung, damit wartende Tasks den Server nicht im Gleichtakt abfragen) |
| `--skip-license-check` | aus | Reservierung überspringen (nur für Methoden ganz ohne Gurobi) |

- **Kein Token bis zum Ablauf:** Pro Methode steht eine Zeile mit
  `status=NO_LICENSE` in der Ergebnisdatei (mit dem letzten Gurobi-Fehler in
  `error`), der Task endet mit Exit-Code 1, Slurm markiert ihn als `FAILED`.
- **Wartezeit sichtbar:** in der Spalte `license_wait_sec`; die einzelnen
  Versuche stehen mit dem Präfix `[license]` in den Slurm-Logs.
- **Ein dauerhafter Konfigurationsfehler** wird ebenfalls bis zum Ablauf
  wiederholt (bis zu 15 Minuten), der Grund steht aber schon nach dem ersten
  Versuch im Log.

**Warum "prüfen" und "reservieren" dasselbe sind:** Eine reine Vorab-Abfrage
wäre nur eine Momentaufnahme -- zwischen Abfrage und Rechenbeginn kann ein
anderer Task das letzte Token wegschnappen. Darum legt `acquire_license()`
die Default-Umgebung von `gurobipy` wirklich an. Sie bleibt für den ganzen
Prozess bestehen und hält das Token; jedes `gp.Model()` ohne `env=` in
deinen Methoden nutzt genau diese Umgebung und verbraucht **kein** zweites
Token.

**Wichtig für deine Methoden:** keine eigenen `gp.Env()`-Objekte zusätzlich
anlegen -- jede Umgebung hält ein eigenes Token.

## Environment: gesperrte Versionen

`requirements.txt` enthält genau die Paketversionen aus deinem
`requirements.lock.txt` (u. a. `gurobipy==12.0.3`, passend zum
Cluster-Modul `optimization/gurobi/12.0.3`). `setup_env.sh` installiert
diese Liste 1:1 in eine venv unter `$WSROOT/venv`.

Ändert sich das Lock-File später (neue Version, neues Paket): Inhalt in
`requirements.txt` übernehmen und `bash setup_env.sh` erneut ausführen.

## Fehlersuche und Nachrechnen

### Wo liegt was?

| Was | Wo |
|---|---|
| Ausgabe eines Tasks | `logs/gurobi_solve_<ARRAY_JOBID>_<TASK_ID>.out` und `.err` |
| Merge-Job | `logs/merge_results_<jobid>.out` |
| Traceback einer Methode (`ERROR`) | `.err` des betreffenden Tasks |
| Teilergebnisse | `results/partial/<instanz>__<methode>.csv` |

Die Job-IDs gibt `submit_all.sh` beim Einreichen aus.

### Nachrechnen einzelner Tasks

Weil `submit_all.sh` immer alles neu rechnet, startest du für einzelne
Tasks den Array-Job direkt mit den gewünschten IDs (Standard-Slurm-Befehle,
hier nicht auf dem Cluster getestet):

```bash
# 1) Welche Tasks sind abgebrochen (Slurm-Ebene)? Die Zahl hinter "_" ist die Task-ID.
sacct -j <ARRAY_JOBID> -X --format=JobID,State,Elapsed | grep -v COMPLETED

# 2) Tasks mit Methoden-Fehler (ERROR) finden -- deren Log enthält einen Traceback:
grep -l Traceback logs/gurobi_solve_<ARRAY_JOBID>_*.err

# 3) Nur diese Tasks erneut rechnen und danach neu zusammenführen:
JOB=$(sbatch --parsable --array=17,23,42 solve_array.sh)
sbatch --dependency=afterany:$JOB merge_results.sh
```

Die vorhandenen Teilergebnisse dieser Tasks werden überschrieben, alle
anderen bleiben erhalten. Das funktioniert **nur**, solange sich
`instances/` und `methods/` seit dem ersten Lauf nicht geändert haben,
sonst zeigen die IDs auf andere Kombinationen.

### Abbrechen

```bash
scancel <ARRAY_JOBID> <MERGE_JOBID>
```

Den Merge-Job mit abbrechen: Er hängt per `afterany` am Array-Job und würde
sonst nach dem Abbruch trotzdem starten.

## Neue Lösungsmethode hinzufügen

1. Datei `methods/meine_methode.py` anlegen (Dateiname **ohne** führenden
   Unterstrich = Methodenname im Grid).
2. Funktion `solve(instance_path, time_limit) -> dict` implementieren,
   siehe `methods/_TEMPLATE_method.py` als Vorlage. Der Rückgabewert muss
   mindestens `objective`, `bound`, `gap`, `runtime_sec` und `status`
   enthalten.
3. Fertig -- die Methode wird beim nächsten `submit_all.sh`-Lauf automatisch
   für jede Instanz mitgerechnet.

**Namenskonvention:** Dateien in `methods/`, die mit `_` beginnen (wie
`_TEMPLATE_method.py`), werden von `grid.py` bewusst ignoriert -- so kann
die Vorlage im Ordner bleiben, ohne versehentlich als echte Methode
mitgerechnet zu werden.
