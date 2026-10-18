# Änderungen

## 0.3.1 – Diagnose-Vorabversion

- Zwei zusätzliche Diagnosemethoden: ältere Windows-Eingabe-APIs und synchrone Fensternachrichten mit Zeitlimit.
- Nachrichten für Maustasten berücksichtigen ein Kindfenster unter dem Mauszeiger.
- MCP-Einzeltests unterstützen die Inventartaste `i`, `escape` und eine begrenzte Haltedauer.
- Zähler heißen Klickversuche und Skillversuche, da die App keine tatsächlich ausgeführte Aktion bestätigt.
- 50 automatisierte Tests, EXE-Vorschau und UTF-8-MCP-Protokolltest. Diese Prüfungen bestätigen keine Funktion im Aion2-Client.

Die fehlende Annahme der Eingaben im laufenden Spiel ist weiterhin offen. Diese Version ist kein bestätigter Fix für den Farmbetrieb.

## 0.3.0 – Diagnose-Vorabversion

- Optionaler lokaler MCP-Anschluss für Status, Aion2-HUD-Aufnahmen, Stopp und begrenzte Eingabetests. Kein Bildschirmwechsel durch den Anschluss.
- Tests dauern höchstens drei Sekunden; Vorschau ist die Vorgabe. Live-Eingaben benötigen freien F9-Hotkey, Spielfokus und ausreichende Windows-Rechte.
- Drei auswählbare Windows-Eingabemethoden: Scancode, virtuelle Tasten und Fensternachrichten. Die beiden SendInput-Methoden unterscheiden sich nur bei Tastatureingaben.
- Separates `Aion2FarmMCP.exe` mit geprüftem stdio-Protokoll; die normale App öffnet die Schnittstelle nur mit `--mcp-control`.
- Abgelaufene, noch nicht bearbeitete Diagnoseanfragen führen keine verspäteten Aktionen aus.

Im erhöhten Live-Test vom 18.10.2026 blieben die Leertaste über alle drei Methoden und abwechselnde Mausklicks über SendInput und Fensternachrichten ohne vom Benutzer beobachtete Reaktion. Spielfokus, F9 und gleiche Rechteebene waren bestätigt; Windows meldete keine Fehler. Der MCP-Anschluss dient zur Untersuchung und behebt die weiterhin fehlende Spieleingabe nicht. Eine konkrete Ursache wie ein bestimmtes Schutzsystem wurde nicht nachgewiesen.

## 0.2.0

- Grundangriffe wechseln zwischen linker und rechter Maustaste. Klickabstand und Haltedauer sind einstellbar; maximal ein freigegebener Skill wird dazwischen eingesetzt.
- Kalibrierte HUD-Prüfung schätzt Mana aus einem farbigen Balken und vergleicht Skill-Symbole mit Referenzen ohne Cooldown. Unbekannte Manakosten, unklare Bilder und geänderte Auflösung sperren betroffene Skills.
- Skills haben eigene Haltedauer und Manakosten. Maustasten lassen sich im Skill-Dialog sichtbar auswählen.
- Diagnose zeigt laufende Spielprozesse und Windows-Rechteebenen. Ein Rechtekonflikt sperrt den Live-Start, bevor Eingaben gezählt werden.
- War F9 beim Öffnen der App durch eine andere Instanz belegt, wird die Registrierung vor dem Live-Start erneut versucht.
- Neustart mit Administratorrechten über die normale Windows-UAC-Abfrage; das aktuelle Profil wird übernommen. Die Bestätigung erfolgt durch den Benutzer.
- Prozessnamenerkennung kann bei nicht lesbarem Vollpfad auf die normale Windows-Prozessliste zurückgreifen.
- HUD-Aufnahmen und Fensterkoordinaten verwenden DPI-bewusste Bildschirmkoordinaten für skalierte Windows-Anzeigen.
- 36 Tests einschließlich Mausklick-Reihenfolge, Mana, Symbol-Cooldown, unbekanntem HUD und unterschiedlichen Rechteebenen.

Die HUD-Erkennung ist ein Bildvergleich und muss auf das eigene Layout eingestellt und im Spiel geprüft werden. Sie bestätigt keine tatsächliche Skill-Ausführung. Gegner- und Ressourcensuche sowie automatische Wegfindung sind nicht enthalten.

## 0.1.0

- Erste Vorabversion mit drei Farmmodi, Klassenprofilen, zeitgesteuerter Skillfolge und Tastaturrouten.
- Vorschau ohne Eingaben, globaler Stopp-Hotkey sowie Laufzeit- und Rundenlimit.
