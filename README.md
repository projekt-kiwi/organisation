# KIWi Consortium – Interaktive Datenbank

Vue 3 App, die die SQLite-Datenbank `kiwi.db` im Browser lädt und durchsuchbar macht.

## Starten

```bash
npm install
npm run dev
```

Im Browser: [http://localhost:5173](http://localhost:5173)

## Filter

- **Schulstufe** – Volksschule, Sekundarstufe I, Sekundarstufe II  
- **Trägerorganisation** – FH OÖ, RISC, RISE2REALITY, SCCH  
- **Workshop** – nur Schulen anzeigen, die einen bestimmten Workshop anbieten  
- **Suche** – Freitext nach Schulname oder Ansprechperson (Name/E-Mail)

Klicken auf eine Schule zeigt Ansprechpersonen und zugeordnete Workshops.

## Build

```bash
npm run build
npm run preview   # Vorschau des Builds
```

Die Datei `public/kiwi.db` wird beim Build nach `dist/` übernommen.
