# Paquet AUR — Singularity

Ce dossier est prêt à devenir le dépôt AUR `singularity-image-optimizer-git`.

Pour tester le paquet localement, lance `makepkg -si` dans ce dossier. Il
clone directement le dépôt public GitHub de Singularity.

Il s'agit volontairement d'un paquet `-git`, puisque le dépôt n'a pas encore
de release taguée. Après avoir poussé cette version de Singularity sur GitHub,
publie uniquement `PKGBUILD` et `.SRCINFO` dans le dépôt AUR correspondant.
