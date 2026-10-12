# Singularity 26.1.0

- Files d’exports statiques PNG, JPEG et WebP sans modifier les originaux.
- Presets intégrés WebP web, JPEG boutique et PNG net.
- Rapports JSON de lot avec chaque fichier, tailles avant/après et erreurs.
- Écriture atomique des images et rapports : une sortie existante n’est remplacée
  qu’une fois l’export complet.
- Mode `--headless --format webp|jpeg|png` et pont Existence alignés sur le
  même moteur d’export.
