# Schulmanager Online für Home Assistant

Eine benutzerdefinierte Home-Assistant-Integration für **Schulmanager Online**
mit lokalem Bridge-Add-on.

⚠️ **KI-unterstütztes Projekt**  
⚠️ **In aktiver Entwicklung**  
Dieses Projekt wird aktiv weiterentwickelt. Funktionen können sich ändern und
Instabilitäten sind möglich.

Das Projekt besteht aus zwei Teilen:

- einer **Home-Assistant Custom Integration**
- einem **lokalen Bridge-Add-on**, das sich bei Schulmanager Online anmeldet und
  die Daten abruft

Die Bridge ist erforderlich, weil der Zugriff auf Schulmanager Online auf
Browser-Automatisierung basiert.

## Funktionen

- Einrichtung direkt über die Home-Assistant-Oberfläche
- auswählbare Schulmanager-Online-Module
- Sensoren für:
  - Konto
  - Stundenplan heute / Woche
  - Hausaufgaben
  - Speiseplan
  - Kalender
  - Klausuren
  - AGs / Veranstaltungen
- manueller Aktualisierungsdienst
- Binary-Sensoren für veraltete Daten und Modulfehler
- optionales gemeinsames Secret zwischen Integration und Bridge
- fertige Dashboard-Cards für Stundenplan und Hausaufgaben

## Unterstützte Module

Schulmanager Online bietet je nach Schule unterschiedliche Module und
Freischaltungen. Diese Integration unterstützt aktuell nur einen Teil davon.
Die Balken zeigen grob den aktuellen Projektstand, nicht die Verfügbarkeit an
deiner Schule.

| Modul in Schulmanager Online | Status | Unterstützung | Hinweis |
| --- | --- | --- | --- |
| Konto | stabil | `██████████` 100 % | Name, Klasse und Basisdaten |
| Stundenplan | gut nutzbar | `████████░░` 80 % | Heute, Woche, Ausfall und Raumänderungen |
| Hausaufgaben | gut nutzbar | `████████░░` 80 % | Datumsgruppen, Fächer und Einträge |
| Speiseplan | teilweise | `██████░░░░` 60 % | Tagesansicht als Sensor |
| Kalender | teilweise | `█████░░░░░` 50 % | einfache Termine |
| Klausuren | teilweise | `████░░░░░░` 40 % | abhängig vom Schulmanager-Online-Layout |
| AGs / Veranstaltungen | experimentell | `███░░░░░░░` 30 % | einfache Einträge |
| Nachrichten / Mitteilungen | nicht unterstützt | `░░░░░░░░░░` 0 % | noch nicht implementiert |
| Krankmeldungen / Abwesenheiten | nicht unterstützt | `░░░░░░░░░░` 0 % | noch nicht implementiert |
| Elternbriefe / Dokumente | nicht unterstützt | `░░░░░░░░░░` 0 % | noch nicht implementiert |

## Repository-Struktur

- `custom_components/schulmanager` - Home-Assistant Custom Integration
- `addons/schulmanager_bridge` - lokales Home-Assistant Add-on
- `docs/markdown-examples` - Dashboard-Beispiele und Card-Konfigurationen

## Schnellinstallation

### 1. Custom Integration mit HACS installieren

In HACS:

- **HACS → Integrationen**
- Menü mit den drei Punkten öffnen
- **Benutzerdefinierte Repositories** auswählen
- Repository: `https://github.com/misc-de/HA-Schulmanager`
- Kategorie: **Integration**
- hinzufügen und anschließend **Schulmanager Online** installieren

Danach Home Assistant neu starten.

### 2. Bridge Add-on Repository installieren

Das Bridge-Add-on wird nicht über HACS installiert. Füge dasselbe GitHub-
Repository im Home-Assistant Add-on Store hinzu:

- **Einstellungen → Add-ons → Add-on Store**
- Menü mit den drei Punkten öffnen
- **Repositories** auswählen
- `https://github.com/misc-de/HA-Schulmanager` hinzufügen

Danach **Schulmanager Online Bridge** aus dem Add-on Store installieren.

### Alternative: manuelle Installation

Add-on-Ordner kopieren:

- `addons/schulmanager_bridge`

in das lokale Add-on-Verzeichnis von Home Assistant:

- `/addons/local/schulmanager_bridge/`

Integrationsordner kopieren:

- `custom_components/schulmanager`

in das Home-Assistant-Konfigurationsverzeichnis:

- `/config/custom_components/schulmanager/`

Danach Home Assistant neu starten.

### 3. Bridge Add-on starten

In Home Assistant öffnen:

- **Einstellungen → Add-ons → Schulmanager Online Bridge**

Add-on installieren und starten.

Optional kann ein gemeinsames Secret gesetzt werden:

```yaml
bridge_secret: "dein-gemeinsames-secret"
```

### 4. Integration hinzufügen

In Home Assistant öffnen:

- **Einstellungen → Geräte & Dienste**
- **Integration hinzufügen**
- **Schulmanager Online** auswählen

Eintragen:

- Benutzername / E-Mail
- Passwort
- Bridge-URL
- gewünschte Module

Die Integration schlägt standardmäßig die IP deines Home-Assistant-Hosts mit
Port `8099` vor.

Beispiel:

```text
http://192.168.0.1:8099
```

Wenn im Add-on ein gemeinsames Secret konfiguriert wurde, muss derselbe Wert in
den Optionen der Integration eingetragen werden.

## Sensoren manuell aktualisieren

Eine Aktualisierung kann über den integrierten Dienst ausgelöst werden:

```yaml
action: schulmanager.refresh
target: {}
data: {}
```

Oder nur für einen bestimmten Config-Entry:

```yaml
action: schulmanager.refresh
target: {}
data:
  entry_id: "DEINE_CONFIG_ENTRY_ID"
```

## Sicherheit

- Port `8099` nicht öffentlich ins Internet freigeben.
- Die Bridge nur im lokalen Netzwerk betreiben.
- Das optionale gemeinsame Secret nutzen, wenn der Bridge-Zugriff zusätzlich
  geschützt werden soll.
- Ausführliches Debug-Logging nicht dauerhaft aktiviert lassen.

## Dashboard-Cards

Fertige Dashboard-Beispiele liegen unter:

- `docs/markdown-examples/`

Für Wochenstundenplan und Hausaufgaben gibt es eigene Lovelace-Cards. Die
Frontend-Ressource muss einmal hinzugefügt werden:

```text
/schulmanager_static/schulmanager-timetable-card.js?v=0.3.25
```

Ressourcentyp: `JavaScript Module`

Stundenplan-Card:

```yaml
type: custom:schulmanager-timetable-card
entity: sensor.YOUR_SCHULMANAGER_SCHEDULE_WEEK_ENTITY
title: Stundenplan
```

Hausaufgaben-Card:

```yaml
type: custom:schulmanager-homework-card
entity: sensor.YOUR_SCHULMANAGER_HOMEWORK_ENTITY
title: Hausaufgaben
```

Beim Hinzufügen über den visuellen Editor bieten die Cards eine Entitätsauswahl
und bevorzugen passende Schulmanager-Online-Sensoren. Die Integration stellt die
Card-Ressource automatisch bereit. Home Assistant bietet jedoch keine stabile
Integrations-API, um beim Installieren oder Aktualisieren ungefragt Dashboard-
Ressourcen oder Karten in Benutzer-Dashboards einzutragen.

Verfügbare Beispiele:

- Stundenplan-Wochenkarte
- Hausaufgaben-Karte
- Debug-Status
- manuelle Aktualisierung
- Sicherheits-Setup

## Tests

Parser-Unit-Tests ausführen:

```bash
python -m pytest tests
```

## Hinweise

- Die Bridge nutzt Browser-Automatisierung und kann Parser-Anpassungen
  benötigen, wenn Schulmanager Online das Layout ändert.
- Schulen können leicht unterschiedliche Seitenstrukturen verwenden.
- Wenn Daten vorübergehend leer sind, behält die Integration nach Möglichkeit
  die letzten erfolgreich geladenen Daten bei.

## Upstream-Referenz

Dieses Projekt basiert auf dem öffentlichen Schulmanager-Online-Scraping-Ansatz aus:

- https://github.com/SchmueI/Schulmanager-API

Das Upstream-Projekt ist unter GPL-3.0 lizenziert. Der GPL-3.0-Lizenztext liegt
in diesem Repository unter `LICENSE.md`.
