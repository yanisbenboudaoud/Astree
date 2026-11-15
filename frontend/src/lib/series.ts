/**
 * Séries de recul précalculées par scripts/build_ui_series.py : entiers 16 bits
 * (dixièmes de point de pourcentage) en base64, alignés sur `calendrier.semaines`.
 * Ce module ne fait que décoder : aucun chiffre n'est estimé dans le navigateur.
 */
import calendrier from '../data/generated/calendrier.json';

export function decoderRecul(base64: string, echelle = calendrier.echelleRecul): number[] {
  const binaire = atob(base64);
  const octets = new Uint8Array(binaire.length);
  for (let i = 0; i < binaire.length; i += 1) octets[i] = binaire.charCodeAt(i);
  const vue = new DataView(octets.buffer);
  const valeurs: number[] = [];
  for (let i = 0; i < octets.length; i += 2) valeurs.push(vue.getInt16(i, true) / echelle);
  return valeurs;
}

/**
 * Série datée du recul, avec le jour exact du point le plus bas inséré à sa place
 * (annexe B, règle 7) : la courbe passe vraiment par le creux annoncé.
 */
export function serieRecul(base64: string, creux?: { date: string; valeur: number }): [string, number][] {
  const valeurs = decoderRecul(base64);
  const serie: [string, number][] = calendrier.semaines.map((d, i) => [d, valeurs[i] ?? 0]);
  if (creux && !serie.some(([d]) => d === creux.date)) {
    const position = serie.findIndex(([d]) => d > creux.date);
    serie.splice(position === -1 ? serie.length : position, 0, [creux.date, creux.valeur]);
  } else if (creux) {
    const i = serie.findIndex(([d]) => d === creux.date);
    serie[i] = [creux.date, creux.valeur];
  }
  return serie;
}

export { calendrier };
