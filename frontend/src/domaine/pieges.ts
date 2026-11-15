/**
 * Exemples prêts pour « Trompez le Greffier » (#69), écrits à partir des pièces du procès affiché :
 * un vrai chiffre, un chiffre inventé, un arrondi faux et un chiffre cité avec la mauvaise pièce.
 * Ce module ne vérifie rien : c'est le Greffier, en Python, qui juge chaque texte (POST /verifier).
 */
import type { PieceContrat } from '../api/contrat';
import type { ResultatTribunal } from '../api/types';
import { pourcent } from '../lib/format';

export interface Piege {
  id: 'vrai' | 'invente' | 'arrondi' | 'piece';
  libelle: string;
  texte: string;
  pieces: string[];
}

function valeursNumeriques(piece: PieceContrat): number[] {
  const feuilles: number[] = [];
  const parcourir = (v: unknown) => {
    if (typeof v === 'number') feuilles.push(v);
    else if (Array.isArray(v)) v.forEach(parcourir);
    else if (v && typeof v === 'object') Object.values(v).forEach(parcourir);
  };
  parcourir(piece.valeurs);
  return feuilles;
}

/** Vrai si un pourcentage écrit avec `decimales` décimales correspond à une valeur de la pièce. */
function present(piece: PieceContrat, pourcentage: number, decimales: number): boolean {
  const facteur = 10 ** decimales;
  return valeursNumeriques(piece).some((v) => Math.round(v * 100 * facteur) === Math.round(pourcentage * facteur));
}

export function pieges(resultat: ResultatTribunal): Piege[] {
  const pieces = resultat.contrat.pieces;
  const simulation = pieces.find((p) => p.outil === 'simuler_portefeuille' && typeof p.valeurs.pire_baisse === 'number');
  if (!simulation) return [];
  const chute = simulation.valeurs.pire_baisse as number;
  const phrase = (valeur: string) => `Avec cette décision, la pire baisse simulée du portefeuille atteint ${valeur}.`;
  const liste: Piege[] = [{ id: 'vrai', libelle: 'Un vrai chiffre', texte: phrase(pourcent(chute)), pieces: [simulation.id] }];

  let invente = Math.round(chute * 100) - 11;
  while (present(simulation, invente, 0)) invente -= 1;
  liste.push({ id: 'invente', libelle: 'Un chiffre inventé', texte: phrase(pourcent(invente / 100, { decimales: 0 })), pieces: [simulation.id] });

  let arrondi = Math.round(chute * 1000) / 10 + 0.1;
  while (present(simulation, arrondi, 1)) arrondi += 0.1;
  liste.push({ id: 'arrondi', libelle: 'Un arrondi faux', texte: phrase(pourcent(arrondi / 100)), pieces: [simulation.id] });

  const autre = pieces.find((p) => p.id !== simulation.id && typeof p.valeurs.rendement_2022_apres === 'number');
  if (autre) {
    const valeur = autre.valeurs.rendement_2022_apres as number;
    if (!present(simulation, valeur * 100, 1)) {
      liste.push({
        id: 'piece',
        libelle: 'La mauvaise pièce',
        // Sans l'année : seul le chiffre, présent dans une autre pièce que celle citée, doit échouer.
        texte: `Rejoué sur l'année de crise, le portefeuille avec la décision aurait fait ${pourcent(valeur)}.`,
        pieces: [simulation.id],
      });
    }
  }
  return liste;
}
