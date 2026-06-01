# Changelog

## 0.3.37
- Server-Blocking umgangen: Die Bridge meldet sich jetzt mit einer realistischen, pro Session rotierenden Browser-Identität an (echter Chrome-User-Agent, passende Sec-CH-UA-Client-Hints und Plattform werden gemeinsam via CDP gesetzt) statt mit einer erkennbaren Bot-Kennung
- Veraltete APIs ersetzt: `datetime.utcnow()` → zeitzonenbewusst, `FlowResult` → `ConfigFlowResult`
- Weniger Log-Rauschen: Setup-/Build-Meldungen von Warnung auf Debug gesenkt
- BUILD-ID-Versionsabgleich korrigiert und im Bump-Skript verankert

## 0.3.36
- Stundenplan-Karte: Dezentere Tageshervorhebung – weichere seitliche Schatten, an die Textfarbe statt an die Primärfarbe gekoppelt

## 0.3.35
- Fix: Lovelace-Ressource der Dashboard-Karte wird erst nach vollständigem Home-Assistant-Start registriert (behebt Timing-Probleme der automatischen Kartenregistrierung)
- Static-Path- und Lovelace-Ressourcen-Registrierung sauber getrennt

## 0.3.34
- Stundenplan-Karte: Seitlicher Schattenüberlauf der Tageshervorhebung per `clip-path` sauber begrenzt

## 0.3.33
- Stundenplan-Karte: Tageshervorhebung mit klarer oberer/unterer Rahmenlinie und weichen seitlichen Schatten (statt Inset-Schatten)

## 0.3.32
- Stundenplan: Pause-Zeilen markieren jetzt den aktuellen Tag
- Stundenplan: Hervorhebung des heutigen Tages mit weichen Schatten

## 0.3.31
- Fix: Automatische Lovelace-Ressourcen-Registrierung der Dashboard-Karten
- Stundenplan: Erste Spalte immer oben ausgerichtet
- Stundenplan: Datum rechtsbündig auf gleicher Höhe wie Wochentag
- Stundenplan: Hervorhebung des heutigen Tages über die gesamte Spalte

## 0.3.30
- DOM-basiertes Parsen der Aktivitäten (robuster als HTML-Textsuche)
- Versionsanzeige in Home Assistant korrekt (Bridge und Integration)

## 0.3.29
- Initiale stabile Version mit Bridge-Integration
- Stundenplan, Hausaufgaben, Mensa, Termine und Klausuren
