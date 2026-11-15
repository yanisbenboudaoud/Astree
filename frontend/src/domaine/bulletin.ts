/**
 * Bulletin du Greffier (#172) : à côté d'un contrôle, combien de fois il a réussi quand on a
 * essayé de le tromper. « Notre Greffier ne vous demande pas de le croire : il affiche son taux
 * de réussite, mesuré, à côté de chacun de ses contrôles. »
 *
 * Les chiffres viennent de `src/data/bulletin.json`, écrit par Python (`validation/bulletin.py`)
 * à chaque commande d'évaluation : l'interface ne calcule rien, elle met en phrase. Les ratés
 * ne sont jamais cachés : un taux sous 100 % est dit tel quel, avec le nombre de cas passés.
 * Sans bulletin (fichier absent), rien ne s'affiche et rien ne casse.
 */
import { date, nombre, pourcent } from '../lib/format';

export interface Taux {
  k: number;
  n: number;
  taux: number;
  rates: number;
  ic95: [number, number];
}

interface MesureJeu {
  issue: number;
  rapport: string;
  date: string;
  pieges: Taux;
  legitimes: Taux;
}

interface MesureExterne {
  issue: number;
  rapport: string;
  date: string;
  seuil_points: number;
  fnb: string[];
  dans_le_seuil: Taux;
  annee_2022: Taux;
}

export interface Bulletin {
  depot: string;
  mesures: {
    verifier_chiffres?: MesureJeu;
    cadre_simulation?: MesureJeu;
    validation_externe?: MesureExterne;
  };
}

/** Une ligne prête à afficher, avec le lien vers le rapport qui la prouve. */
export interface Epreuve {
  texte: string;
  lien: string;
  /** Aucun raté : tous les pièges vus et tous les arguments légitimes admis. */
  complet: boolean;
}

// import.meta.glob plutôt qu'un import : sans fichier, l'objet est vide et le build passe.
const fichiers = import.meta.glob<Bulletin>('../data/bulletin.json', { eager: true, import: 'default' });
export const BULLETIN: Bulletin | null = Object.values(fichiers)[0] ?? null;

/** Ce que chaque contrôle du Greffier a dû repérer, dit en clair. */
const EPREUVES: Record<string, { objet: string; verbe: string; legitimes: string }> = {
  verifier_chiffres: { objet: 'chiffres inventés', verbe: 'détectés', legitimes: 'arguments aux chiffres exacts' },
  cadre_simulation: { objet: 'conseils et promesses', verbe: 'bloqués', legitimes: 'arguments légitimes' },
};

const lienRapport = (bulletin: Bulletin, rapport: string) => `${bulletin.depot}${rapport}`;

/** « 31 sont passés » / « 1 est passé ». */
const passes = (n: number) => `${n} ${n > 1 ? 'sont passés' : 'est passé'} sans être ${n > 1 ? 'vus' : 'vu'}`;

/** La ligne du bulletin sous un contrôle du Greffier, ou `null` s'il n'a pas été mesuré. */
export function epreuveDuControle(regle: string, bulletin: Bulletin | null = BULLETIN): Epreuve | null {
  const libelles = EPREUVES[regle];
  const mesure = bulletin?.mesures[regle as 'verifier_chiffres' | 'cadre_simulation'];
  if (!bulletin || !libelles || !mesure) return null;
  const { pieges, legitimes } = mesure;
  const tauxPieges = pieges.rates ? ` (${pourcent(pieges.taux, { decimales: 0 })}) ; ${passes(pieges.rates)}` : '';
  const refuses = legitimes.rates ? ` ; ${legitimes.rates} ${legitimes.rates > 1 ? 'refusés' : 'refusé'} à tort` : '';
  return {
    texte: `Mis à l’épreuve : ${pieges.k} ${libelles.objet} ${libelles.verbe} sur ${pieges.n}${tauxPieges}. `
      + `${legitimes.k} ${libelles.legitimes} admis sur ${legitimes.n}${refuses}. Mesure du ${date(mesure.date)}.`,
    lien: lienRapport(bulletin, mesure.rapport),
    complet: pieges.rates === 0 && legitimes.rates === 0,
  };
}

/** La ligne sur la validation externe des rendements, pour le tiroir d'une pièce de simulation. */
export function epreuveDesDonnees(bulletin: Bulletin | null = BULLETIN): Epreuve | null {
  const mesure = bulletin?.mesures.validation_externe;
  if (!bulletin || !mesure) return null;
  const { dans_le_seuil: total, annee_2022: crise } = mesure;
  const hors = total.rates ? ` ; ${total.rates} au-delà, ${total.rates > 1 ? 'expliqués' : 'expliqué'} dans le rapport` : '';
  return {
    texte: `Les prix de départ ont été confrontés aux rendements publiés par les émetteurs de ${mesure.fnb.length} FNB : `
      + `${total.k} années sur ${total.n} à moins de ${nombre(mesure.seuil_points, 2)} point d’écart${hors}, `
      + `dont 2022 : ${crise.k} sur ${crise.n}. Mesure du ${date(mesure.date)}.`,
    lien: lienRapport(bulletin, mesure.rapport),
    complet: total.rates === 0,
  };
}
