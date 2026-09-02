# Schulmanager Online für Home Assistant

Eine benutzerdefinierte Home-Assistant-Integration für **Schulmanager Online**
mit lokalem Bridge-Add-on.

⚠️ **KI-unterstütztes Projekt**  

Dieses Projekt wird aktiv weiterentwickelt. Funktionen können sich ändern und
Instabilitäten sind möglich.

Das Projekt besteht aus mehreren Home-Assistant-Bausteinen:

- einer **Home-Assistant Custom Integration**
- einem **lokalen Bridge-Add-on**, das sich bei Schulmanager Online anmeldet und
  die Daten abruft
- optionalen **Lovelace Dashboard-Cards** für Stundenplan und Hausaufgaben

Die Bridge holt die Daten seit Version 0.3.41 über dieselbe JSON-Schnittstelle,
die auch die Weboberfläche von Schulmanager Online nutzt. Ein Browser wird dafür
nicht mehr gestartet: Ein Abruf dauert Bruchteile einer Sekunde statt rund 25
Sekunden, und Layout-Änderungen an der Website können ihn nicht mehr brechen.
Als eigenes Add-on läuft sie weiterhin, damit die Anmeldung und das
Zwischenspeichern der Sitzung außerhalb des Home-Assistant-Prozesses liegen.

## Was wird wodurch installiert?

Home Assistant trennt Integrationen, Add-ons und Dashboard-Ressourcen technisch
voneinander. Deshalb gibt es keine echte Alles-in-einem-Installation über HACS.

| Baustein | Installation | Zweck |
| --- | --- | --- |
| Custom Integration | HACS Custom Repository | erzeugt Sensoren, Dienste und Optionen in Home Assistant |
| Bridge Add-on | Home-Assistant Add-on Store Repository | meldet sich bei Schulmanager Online an und liefert Daten an die Integration |
| Lovelace Cards | Dashboard-Ressource | zeigt Stundenplan und Hausaufgaben als fertige Cards im Dashboard an |

Für HACS und Add-on Store wird dieselbe GitHub-Adresse verwendet:

```text
https://github.com/misc-de/HA-Schulmanager
```

Die Integration stellt die Card-Datei bereit, aber Home Assistant bietet keine
stabile Integrations-API, um Dashboard-Ressourcen oder Karten ungefragt beim
Installieren oder Aktualisieren einzutragen. Die Ressource muss daher einmal im
Dashboard hinzugefügt werden.

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
| Konto | stabil | `██████████` 100 % | Name und zugeordnete Schüler, kommen direkt aus der Anmeldung |
| Stundenplan | stabil | `█████████░` 90 % | Heute und Woche mit Fach, Lehrer und Raum; Entfall und Vertretung werden gekennzeichnet |
| Kalender | gut nutzbar | `████████░░` 80 % | Termine mit Datum, Uhrzeit und Titel |
| Hausaufgaben | gut nutzbar | `███████░░░` 70 % | Datumsgruppen und Fächer; die Feldzuordnung ist noch nicht gegen echte Einträge geprüft |
| Klausuren | gut nutzbar | `███████░░░` 70 % | Datum, Zeitraum und Fach; ebenfalls noch nicht gegen echte Einträge geprüft |
| AGs / Veranstaltungen | experimentell | `████░░░░░░` 40 % | über die Wahlkurse des Schülers; noch nicht gegen echte Einträge geprüft |
| Speiseplan | derzeit ohne Daten | `░░░░░░░░░░` 0 % | seit 0.3.41 ohne Zuordnung zur Schnittstelle – siehe Hinweis unten |
| Elternbriefe / Dokumente | nicht unterstützt | `░░░░░░░░░░` 0 % | Schnittstelle ist vorhanden, aber noch nicht angebunden |
| Nachrichten / Mitteilungen | nicht unterstützt | `░░░░░░░░░░` 0 % | noch nicht implementiert |
| Krankmeldungen / Abwesenheiten | nicht unterstützt | `░░░░░░░░░░` 0 % | noch nicht implementiert |

> **Speiseplan:** Mit dem Wechsel auf die JSON-Schnittstelle in Version 0.3.41
> ist der Speiseplan vorübergehend entfallen – für dieses Modul ist noch keine
> passende Schnittstelle gefunden. Der Sensor existiert weiterhin, bleibt aber
> leer und meldet den Grund über `meta.module_errors`. Alle übrigen Module
> liefern Daten wie zuvor.

Module, die eine Schule nicht freigeschaltet hat, liefern ebenfalls leere
Listen – das ist kein Fehler der Integration.

## Wie die Daten geholt werden

1. Die Integration ruft die Bridge über HTTP auf (Standard: Port `8099`).
2. Die Bridge meldet sich bei Schulmanager Online an und erhält ein Token, das
   sie rund eine Stunde lang weiterverwendet. Die Anmeldung selbst ist
   rechenintensiv und fällt deshalb nur selten an.
3. Alle ausgewählten Module werden in **einer** gebündelten Anfrage geholt.
4. Die Bridge gibt normalisiertes JSON zurück, die Integration aktualisiert die
   Sensoren.

Ein einzelnes fehlerhaftes Modul beendet den Abruf nicht: Es wird in
`meta.module_errors` vermerkt, während die übrigen Module normal weiterlaufen.

## Repository-Struktur

- `custom_components/schulmanager` - Home-Assistant Custom Integration
- `addons/schulmanager_bridge` - lokales Home-Assistant Add-on
  (`api_client.py` spricht mit der JSON-Schnittstelle, `bridge_server.py`
  stellt sie Home Assistant zur Verfügung)
- `docs/markdown-examples` - Dashboard-Beispiele und Card-Konfigurationen

## Installation

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

### 3. Dashboard-Cards laden

Die Integration lädt die Dashboard-Cards automatisch als Frontend-Modul:

```text
/schulmanager_static/schulmanager-timetable-card.js?v=<installierte Version>
```

Die Versionsangabe hängt die Integration selbst an, damit der Browser nach einem
Update nicht die alte Datei aus dem Cache nimmt.

Nach einem Update ist ein Home-Assistant-Neustart und ein harter Browser-Reload
oft nötig. Falls die Cards trotzdem nicht gefunden werden, kann dieselbe URL
zusätzlich manuell als Dashboard-Ressource mit Typ `JavaScript Module`
eingetragen werden.

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

### 4. Bridge Add-on starten

In Home Assistant öffnen:

- **Einstellungen → Add-ons → Schulmanager Online Bridge**

Add-on installieren und starten.

Optional kann ein gemeinsames Secret gesetzt werden:

```yaml
bridge_secret: "dein-gemeinsames-secret"
```

### 5. Integration hinzufügen

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
- **Gemeinsames Secret dringend empfohlen:** Ohne gesetztes `bridge_secret`
  nimmt die Bridge Anfragen ungeprüft entgegen. Die Anmeldedaten werden bei
  jedem Abruf unverschlüsselt (HTTP) an die Bridge übertragen – im lokalen Netz
  üblich, aber das Secret verhindert, dass andere Geräte im selben Netz die
  Bridge ansprechen können.
- Ausführliches Debug-Logging nicht dauerhaft aktiviert lassen.

## Dashboard-Cards

Fertige Dashboard-Beispiele liegen unter:

- `docs/markdown-examples/`

Für Wochenstundenplan und Hausaufgaben gibt es eigene Lovelace-Cards. Die
Integration lädt die Frontend-Ressource normalerweise automatisch:

```text
/schulmanager_static/schulmanager-timetable-card.js?v=<installierte Version>
```

Falls Home Assistant die Cards nicht automatisch lädt, kann diese URL manuell
als Dashboard-Ressource mit Typ `JavaScript Module` hinzugefügt werden.

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

```bash
python -m pytest tests
```

Die Suite läuft vollständig offline: `tests/conftest.py` stellt Stubs für
`aiohttp` und `homeassistant` bereit, sodass für die Tests keine
Produktivabhängigkeiten installiert sein müssen. Das Mapping der JSON-API wird
gegen echte, aufgezeichnete API-Antworten geprüft.

## Hinweise

- Die Bridge liest keine HTML-Seiten mehr, sondern die JSON-Schnittstelle.
  Änderungen am Seitenlayout von Schulmanager Online wirken sich damit nicht
  mehr auf die Datenabfrage aus.
- Die Schnittstelle ist nicht offiziell dokumentiert. Sie kann sich ändern —
  Fehler zeigen sich dann aber als eindeutiger HTTP-Status statt als still
  leerlaufende Sensoren.
- Welche Module eine Schule freigeschaltet hat, ist von Schule zu Schule
  verschieden. Nicht freigegebene Module liefern leere Listen.
- Wenn Daten vorübergehend leer sind, behält die Integration nach Möglichkeit
  die letzten erfolgreich geladenen Daten bei.

## Upstream-Referenz

Dieses Projekt ging ursprünglich vom öffentlichen Schulmanager-Online-Scraping-Ansatz aus:

- https://github.com/SchmueI/Schulmanager-API

Seit Version 0.3.41 wird nicht mehr gescrapt, sondern die JSON-Schnittstelle
verwendet. Der Lizenzbezug bleibt davon unberührt.

Das Upstream-Projekt ist unter GPL-3.0 lizenziert. Der GPL-3.0-Lizenztext liegt
in diesem Repository unter `LICENSE.md`.
