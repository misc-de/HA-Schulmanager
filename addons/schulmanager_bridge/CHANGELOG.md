# Changelog

## 0.3.41
- **Umstieg auf die Schulmanager-JSON-API.** Die Bridge liest die Daten nicht mehr aus der gerenderten Webseite, sondern über dieselbe JSON-Schnittstelle, die auch die Weboberfläche nutzt (`/api/get-salt` → `/api/login` → `/api/calls`). Alle Module werden in **einem** gebündelten Request geholt
- **Abruf dauert jetzt unter einer Sekunde statt rund 25 Sekunden.** Die Anmeldung (PBKDF2, ~4 s) fällt nur noch etwa einmal pro Stunde an, weil das JWT zwischen den Abrufen im Speicher gehalten und erst kurz vor Ablauf erneuert wird
- **Chromium und Selenium entfallen komplett** – das Add-on-Image enthält keinen Browser mehr, es gibt keine Browser-Profile, keine Profil-Sperren und keine Selektor-Abhängigkeit. Genau der Fehler aus 0.3.40 („Schulmanager hat ein Element umbenannt") kann so nicht mehr auftreten
- Fehler sind jetzt eindeutig: ein abgelehnter Login liefert HTTP 401, ein einzelnes fehlerhaftes Modul nur einen Eintrag in `meta.module_errors`, während die übrigen Module normal weiterlaufen
- Der Kontoname wird wieder korrekt gefüllt (kam aus dem Login-Ergebnis statt aus der geparsten Kontoseite) – behebt den `IndexError` des alten Parsers
- Das Datenformat ist unverändert: Sensoren, Binärsensoren und die Stundenplan-Karte brauchen keine Anpassung
- `scraper_client.py` bleibt vorerst im Repository (nicht mehr im Image), damit ein Rückzug auf das Scraping möglich bleibt
- Bekannte Einschränkung: Der Speiseplan (`meal`) hat noch keine API-Zuordnung und liefert eine leere Liste mit Hinweis in `meta.module_errors`

## 0.3.40
- **Fix: „Authentication failed" ohne Grund.** Der Login galt nur dann als erfolgreich, wenn das Element `#accountDropdown` erschien. Schulmanager hat die Seite geändert – der Login funktionierte, aber das Element fehlte, und die Bridge meldete fälschlich ungültige Zugangsdaten. Home Assistant hat daraufhin die Abfrage komplett gestoppt und eine Neuanmeldung verlangt, die nichts geändert hätte
- Der Login wird jetzt am tatsächlichen Ergebnis gemessen: Dashboard-Container **oder** Account-Menü **oder** „Formular weg und weggeleitet". Als abgelehnte Zugangsdaten zählt nur noch eine echte Fehlermeldung des Login-Formulars; alles andere ist ein Verbindungsfehler, nach dem Home Assistant beim nächsten Intervall normal weiterläuft
- Ein defektes persistentes Profil wird jetzt auch nach einem fehlgeschlagenen Login-Versuch zurückgesetzt (bisher nur, wenn die Seite gar nicht lud)
- **Fix: Falsches `bridge_secret` ergab HTTP 500 statt 401.** Die `HTTPException` der Middleware lag außerhalb der Fehlerbehandlung von FastAPI. Die Bridge antwortet jetzt mit einem echten 401 samt `X-Schulmanager-Error: bridge_secret`, und die Integration behandelt das als Konfigurationsfehler statt als falsche Schulmanager-Zugangsdaten – ohne Neuanmelde-Dialog
- Bessere Diagnose: Der Seitenauszug im Log zeigt jetzt den sichtbaren Seitentext statt immer desselben Boilerplates aus dem `<head>` der Angular-App

## 0.3.39
- Fix: Persistente Session konnte „Login form could not be loaded" (502) auslösen, wenn das Dashboard nach Kaltstart langsam rendert. Der Login wartet jetzt auf Dashboard **oder** Login-Formular (je nachdem, was zuerst erscheint), statt eine aktive Session nach kurzem Timeout fälschlich zu verwerfen
- Ein defektes persistentes Profil wird nach fehlgeschlagenem Login automatisch zurückgesetzt, sodass der nächste Abruf sauber neu einloggt
- Bessere Diagnose: Bei fehlgeschlagenem Login werden URL, Seitentitel und ein Seitenauszug geloggt (hilft, Server-Block/Captcha von langsamer Ladezeit zu unterscheiden)

## 0.3.38
- Persistente Browser-Session: Die Bridge meldet sich nicht mehr bei jedem Abruf neu mit Benutzername + Passwort an, sondern hält die Schulmanager-Session (Cookies + Token) in einem dauerhaften Chromium-Profil pro Benutzer. Folge-Abrufe überspringen den Login komplett – deutlich weniger Login-Traffic und geringeres Block-Risiko
- Login-Validierung nutzt weiterhin ein Wegwerf-Profil (kein dauerhafter State, keine Konflikte mit laufenden Abrufen)
- Robustheit: Verwaiste Chromium-Profil-Sperren eines abgestürzten Vorlaufs werden vor dem Start bereinigt

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
