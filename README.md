# AION2 Farm

Konfigurierbare Windows-App für Kampf- und Sammelroutinen. Abwechselnde Links-/Rechtsklicks, Skills mit kalibrierter Mana- und Symbolprüfung, aufnehmbare Tastaturrouten und klassenunabhängige Profile. Deutsche Oberfläche, lokale JSON-Profile, keine Anmeldung.

**Version 0.3 verwendet zeitgesteuerte Routen und eine bildbasierte Freigabe für Skills.** Die HUD-Prüfung benötigt eine Kalibrierung auf das eigene Layout. Sie schätzt Mana aus dem Balken und vergleicht Skill-Symbole mit einer Referenz ohne Cooldown. Das ist eine visuelle Näherung, keine Abfrage exakter Spielzustände. Gegner, Ressourcen, Lebenspunkte, Hindernisse, Position und Inventar werden nicht erkannt; es gibt keine automatische Wegfindung. Im bisherigen Live-Test reagierte Aion2 trotz von Windows angenommener Eingaben nicht. Die Ursache ist noch offen; die App ist eine Diagnose-Vorabversion.

Aion2 untersagt Bots und unbeaufsichtigte Makros; ein Einsatz kann zur Accountsperre führen. Siehe [offizielle Regeln](https://help.plaync.com/faq/aion2global/view?faqNo=7164). Die App verwendet normale Windows-Eingaben. Sie verändert keine Spieldateien und bietet keine Umgehung von Schutzsystemen.

## Start

1. Unter **Releases** `Aion2Farm.exe` herunterladen und starten. Windows 10/11, x64; Python wird für die EXE nicht benötigt. Die EXE ist nicht codesigniert.
2. Profilname und Klasse eintragen. Alle Klassen verwenden denselben Ablauf; Tasten, Skills und Zeiten sind je Profil frei konfigurierbar. Die eingebauten Belegungen sind Beispiele und müssen angepasst werden.
3. Den Prozessnamen des Spielfensters prüfen, standardmäßig `Aion2.exe`. Unter der App steht der Dateiname des jeweils aktiven Fensters.
4. **Kampf**, **Sammeln** oder **Kombiniert** auswählen und die jeweiligen Tasten einstellen.
   Unter **Kampf & Skills** ist **Links / Rechts abwechselnd** standardmäßig aktiv. Die Maustasten sind Grundangriffe; maximal ein freigegebener Skill wird dazwischen eingesetzt. Klickabstand und Haltedauer sind einstellbar.
5. Mit eingeschalteter **Vorschau** starten. Diese läuft zehnfach beschleunigt, protokolliert die Aktionen und sendet keine Eingaben. Die Startverzögerung läuft in Echtzeit.
6. Profil speichern. Für echte Eingaben die Vorschau deaktivieren, F8 drücken und innerhalb der Startverzögerung ins Spielfenster wechseln. F9 stoppt jederzeit.

## Diagnose und Administratorrechte

Vor einem Live-Start prüft die App die Rechteebene der laufenden Spielprozesse. Ein mit Administratorrechten laufendes Spiel kann normale Windows-Eingaben einer App mit niedrigeren Rechten blockieren ([Microsoft: SendInput und UIPI](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-sendinput)).

Unter **Diagnose → Neu prüfen** stehen Prozessname, PID und Rechteebenen. Bei unterschiedlichen Rechten **Mit Administratorrechten neu starten** wählen und die normale Windows-UAC-Abfrage selbst bestätigen. Das aktuelle Profil wird übernommen. Bei Ablehnung bleibt die bisherige App offen. Es werden keine Windows-Sicherheitseinstellungen verändert und keine Schutzfunktionen umgangen.

Nur eine Version der App gleichzeitig öffnen, damit die globalen Hotkeys frei sind. Der Mauszeiger muss für Mauskampf über der Spielwelt stehen; außerhalb des Spielfensters wird der Mausklick abgebrochen.

## Mana und Cooldown-Symbole kalibrieren

Die standardmäßig aktive Option **Skills nur bei ausreichendem Mana und visuell bereitem Symbol** sperrt unvollständig eingerichtete Skills. Grundangriffe können unabhängig davon weiterlaufen. In der Vorschau wird die Skill-Freigabe simuliert; sie ist kein Test der HUD-Erkennung.

1. In **Kampf & Skills** pro Skill die tatsächlichen **Manakosten**, die Haltedauer, eine Pause zum Ausführen und eine minimale Cooldown-Zeit eintragen. **Leer bedeutet unbekannt und sperrt den Skill.** Bei tatsächlich kostenlosen Skills ausdrücklich `0` eintragen. Die Zeitgeber ergänzen die Bildprüfung.
2. Unter **HUD-Erkennung** das maximale Mana laut Spiel eintragen.
3. Bei vollem Mana **Vollen Manabalken wählen** drücken und während des Countdowns ins Spiel wechseln. Im anschließend angezeigten Standbild einen dünnen, farbigen Streifen über die volle Breite des Manabalkens markieren. Zahlen, Rahmen und Verzierungen auslassen.
4. Einen Skill im Auswahlfeld wählen. Bei bereitem Skill ohne Cooldown **Bereites Skill-Symbol wählen** drücken und ins Spiel wechseln. Nur das innere Symbol ohne Tastenbeschriftung und äußeren Rahmen markieren. Für jeden Skill wiederholen.
5. **HUD prüfen** wählen und ins Spiel wechseln. Nach dem Countdown stehen geschätztes Mana und die Zahl visuell bereiter Symbole im Status und Log. Dieser Test sendet keine Eingaben. Anschließend Profil speichern.

Für die Skill-Freigabe müssen zwei aufeinanderfolgende Aufnahmen zum bereiten Symbol passen und ausreichend geschätztes Mana vorhanden sein. Kürzlich ausgelöste Skills reservieren ihr Mana kurzzeitig; ein zusätzlicher Puffer von 2 % vermeidet knappe Schätzungen. Bei fehlender Kalibrierung, unlesbarem HUD, unbekannten Kosten oder geänderter Fensterauflösung bleiben die betroffenen Skills aus.

Beleuchtung, Icon-Animationen, Überlagerungen und Theme-/HUD-Änderungen können Bildvergleiche verfälschen. Die Erkennung muss im eigenen Spielbetrieb überprüft werden; sie bestätigt nicht, dass ein Tastendruck vom Spiel angenommen wurde. Nach Auflösungs-, HUD- oder Maximalmana-Änderungen die Kalibrierung beziehungsweise den Maximalwert anpassen. Die Referenzen werden nur lokal im Profil gespeichert.

## Routen aufnehmen

- Im Reiter **Route** die aufzunehmenden Bewegungstasten einstellen. Es werden ausschließlich diese Tastaturtasten und nur während des Spielfokus aufgezeichnet.
- F10 startet nach der eingestellten Verzögerung die Aufnahme. Vorher stillstehen und ins Spiel wechseln.
- Route mit der Tastatur ablaufen. Die Aufzeichnung enthält Tastenkombinationen, Haltezeiten und Wartezeiten.
- Am gewünschten Punkt alle Bewegungstasten loslassen: **F6** setzt einen Kampfpunkt, **F7** einen Sammelpunkt. Die Dauer kommt aus dem jeweiligen Reiter. Danach weiterlaufen; die Kampf- oder Sammelaktion während der Aufnahme muss nicht selbst ausgeführt werden.
- F10 beendet die Aufnahme. F9 beendet sie ebenfalls und behält das Aufgenommene. Neue Aufnahmen werden an die bestehende Route angehängt.
- Die Route prüfen und speichern. Schritte lassen sich hinzufügen, bearbeiten, verschieben oder entfernen.
- Kamerabewegungen und Mausklicks werden **nicht aufgenommen**. Einen Schritt **Maus bewegen** ergänzen, bei Bedarf mit `rightmouse` als gehaltener Taste. X und Y sind relative Mausbewegungen und müssen auf die Empfindlichkeit des Spiels abgestimmt werden.
- Die Route muss zum Startpunkt zurückführen; jede Runde beginnt dort erneut. Feste Wege können durch Kollisionen, unterschiedliche Laufgeschwindigkeit oder Kameraposition abweichen.

Im Kampfmodus werden Sammelpunkte übersprungen, im Sammelmodus Kampfpunkte. Der kombinierte Modus führt beide aus. Eine Route braucht für jeden ausgewählten Modus mindestens einen passenden Aktionspunkt. Ohne Route bleibt der Charakter am aktuellen Standort und wiederholt die ausgewählten Aktionen.

## Klassenprofile und Skills

- Frei wählbarer Klassenname und beliebig viele Profile; keine hart codierten Klassenrotationsdaten.
- Skills werden reihum zwischen den abwechselnden Mausklicks eingesetzt. Pro Skill gelten minimale Cooldown-Zeit, Haltedauer, Pause und – bei aktiver HUD-Prüfung – Manakosten und Symbolreferenz. Die Symbolprüfung liest keine Prozessspeicherwerte.
- Auch Buffs oder Verbrauchsgegenstände lassen sich als Skill mit passendem Intervall eintragen. Es gibt keine Lebenspunkterkennung für bedarfsabhängige Heilung.
- Tasten: `a`–`z`, `0`–`9`, `tab`, `space`, `enter`, `escape`, `shift`, `ctrl`, `alt`, Pfeiltasten, `home`, `end`, `insert`, `delete`, `pageup`, `pagedown`, `backspace`, `leftmouse`, `rightmouse`, `middlemouse` und F1–F12 außer F6–F10. Kombinationen etwa `shift+1` oder `ctrl+2`. Sonderzeichen und Numpad-Tasten werden derzeit nicht unterstützt.
- Zielwechsel und Looten sind zeitgesteuert. Ein leeres Tastenfeld deaktiviert diese beiden Aktionen.
- Lokale Profile: `%LOCALAPPDATA%\Aion2Farm\profiles`. Über Import/Export lassen sich JSON-Profile übertragen. Profile führen keinen Code aus.

| Hotkey | Funktion |
| --- | --- |
| F6 | Kampfpunkt während der Aufnahme |
| F7 | Sammelpunkt während der Aufnahme |
| F8 | Lauf starten |
| F9 | Lauf/Aufnahme stoppen, gehaltene Tasten freigeben |
| F10 | Aufnahme starten/beenden |

Die fünf Hotkeys werden von der App global reserviert. Bei Fokusverlust stoppt ein Live-Lauf. Live-Start ist gesperrt, wenn F9 bereits von einem anderen Programm belegt ist. Standardmäßig endet ein Lauf nach 30 Minuten; zusätzlich ist ein Rundenlimit möglich. Beide Limits können bewusst auf 0 gesetzt werden.

## Lokale MCP-Diagnose

`Aion2FarmMCP.exe` ist eine optionale stdio-Schnittstelle für einen MCP-Client. Die Farm-App muss gleichzeitig mit `--mcp-control` laufen:

```powershell
.\Aion2Farm.exe --mcp-control
```

Falls das Spiel erhöht läuft, die Farm-App über **Diagnose → Mit Administratorrechten neu starten** neu öffnen und die UAC-Abfrage selbst bestätigen. Der Diagnoseanschluss bleibt dabei aktiv. Vorher andere Farm-App-Instanzen schließen, damit F9 frei ist.

Der MCP-Client startet `Aion2FarmMCP.exe` als stdio-Server ohne zusätzliche Argumente. Für die Entwicklung ist alternativ `python -m aion2_farm.mcp_server` im Projektverzeichnis möglich. Unterstützte Protokollversionen: 2024-11-05 bis einschließlich 2025-11-25.

| Werkzeug | Wirkung |
| --- | --- |
| `farm_status` | Version, Rechte, Vordergrundprozess, Profil, Zähler und letzte Logzeilen lesen |
| `farm_capture_hud` | Bild des Aion2-Spielfensters im Vordergrund lesen, maximal 1600 × 1000 Pixel |
| `farm_test_input` | Einzelne Testtaste oder abwechselnde Mausklicks für höchstens drei Sekunden ausführen |
| `farm_stop` | Lauf stoppen und von der App gehaltene Eingaben freigeben |

`farm_test_input` verwendet standardmäßig die Vorschau. Ein Live-Test benötigt ausdrücklich `"preview": false`, freien F9-Hotkey, ausreichende Rechte und das Spiel im Vordergrund. Beispielargumente: `{"key":"alternate_mouse","method":"scancode","seconds":2,"preview":false}`. Erlaubt sind die Maustasten links/rechts, `1`, `2`, `3`, `tab` und `space`; keine beliebigen Tastaturfolgen oder Programme. Das Testprofil wird vorübergehend verwendet und verändert das gespeicherte Profil nicht. Während dieses einzelnen Eingabetests werden keine regulären Skills, Routen, Zielwechsel oder Loot-Aktionen ausgeführt.

Die Methoden `scancode` und `virtual` verwenden Windows `SendInput`; bei Maustasten sind sie gleich. `messages` sendet normale Fenster-Eingabenachrichten. Moderne Spiele können diese Eingaben ignorieren. Weder ein erfolgreicher API-Aufruf noch hochgezählte Aktionen bestätigen eine Reaktion des Charakters.

Im lokalen Live-Test vom 18.10.2026 liefen Spiel und App mit Administratorrechten, F9 war registriert und der Spielfokus blieb erhalten. Leertaste über alle drei Methoden sowie Links-/Rechtsklicks über SendInput und Fensternachrichten wurden ohne Windows-Fehler abgeschlossen. Der Benutzer bestätigte bei allen Tests keine Reaktion des Charakters. Die Eingabe in diesem Client funktioniert damit weiterhin nicht; ein bestimmtes Schutzsystem als Ursache wurde nicht nachgewiesen. Die Testbilder und persönlichen Logs werden nicht veröffentlicht.

Die Schnittstelle aktiviert keine Fenster und bewegt den Mauszeiger nicht selbstständig. Sie ist ausschließlich an `127.0.0.1` gebunden und durch ein zufälliges Sitzungstoken geschützt. Das Token liegt nur lokal in `%LOCALAPPDATA%\Aion2Farm\control-session.json`; diese Datei nicht teilen. Der Anschluss kann nur Aion2 testen, Bilder dieses Vordergrundfensters lesen und den eigenen Lauf stoppen. Beim Beenden der App wird er geschlossen. Ohne `--mcp-control` wird kein Anschluss geöffnet.

## Entwicklung

Python 3.12 unter Windows mit Tkinter und Pillow:

```powershell
python -m pip install -r requirements.txt
python run.py
python -m unittest discover -s tests -v
python run.py --smoke-test --report artifacts/smoke.json
```

Für den letzten Befehl zuerst `artifacts` anlegen. Der Smoke-Test prüft die komplette Vorschau über die Oberfläche; globale Hooks und echte Eingaben bleiben dabei deaktiviert. Optional kann `--screenshot artifacts/app.png` mit installiertem Pillow verwendet werden.

Windows-EXE bauen, testen und Prüfsumme erzeugen:

```powershell
./build.ps1
```

Das Skript installiert die Build-Abhängigkeiten in `.venv`. GitHub Actions führt denselben Build mit Kern-, Windows-Adapter- und EXE-Vorschautests aus.

Getestet werden unter anderem Modusauswahl, Profilimport, Route mit Tastenkombinationen, Rotation, Zeitlimit, Fokusverlust und Stopp während einer gehaltenen Taste. Automatisierte Tests erzeugen keine Spieleingaben. Ein erfolgreicher Build bestätigt keine Funktion im Aion2-Client.
