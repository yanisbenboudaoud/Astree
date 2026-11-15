/**
 * Questionnaire investisseur et Pacte construit à partir des réponses (#84, #86).
 *
 * Les questions viennent du pipeline
 * (`pipeline.questionnaire.questions`, précalculées dans generated/questionnaire.json) :
 * aucun texte de question ni chiffre n'est écrit dans l'interface.
 *
 * Le barème tourne en Python, jamais dans le navigateur :
 * - mode direct : `POST /profil` de la Lambda, avec `apercu: true` pour l'aperçu (rien n'est
 *   rangé), puis sans pour signer (profil rangé dans S3, vues renvoyées) ;
 * - mode démonstration : seul l'exemple préenregistré (docs/exemples/reponses_questionnaire.json)
 *   peut être construit ; son résultat a été calculé par le même code. Toute autre saisie
 *   est refusée avec un message clair, plutôt que d'inventer un Pacte.
 */
import questionnaire from '../data/generated/questionnaire.json';
import { MODE_DIRECT, URL_API, lireErreur } from './config';
import { enregistrerProfilCree, type VuesProfil } from './donnees';
import type { Profil, DonneesCalibrage } from './types';

export interface ChoixQuestion {
  id: string;
  libelle: string;
}

export interface Question {
  id: string;
  nom_court: string;
  section: string;
  type: 'choix' | 'choix_multiples' | 'texte';
  obligatoire?: boolean;
  libelle: string;
  justification?: string;
  choix?: ChoixQuestion[];
  longueur_max?: number;
}

export type ValeurReponse = string | string[];
export type Reponses = Record<string, ValeurReponse>;

export interface LigneSaisie {
  ticker: string;
  poids: number;
}

/** Tout ce que l'utilisateur saisit, dans le format de `POST /profil`. */
export interface SaisiePacte {
  nom: string;
  capital: number;
  portefeuille: LigneSaisie[];
  reponses: Reponses;
  /** Seuils choisis par l'utilisateur avant de signer : `{ "<id de règle>": valeur }`. */
  modifications?: Record<string, number>;
}

/** Règle du Pacte telle que Python l'écrit dans le fichier profil (personas/schema_pacte.json). */
export interface ReglePacte {
  id: string;
  type: 'pire_baisse_max' | 'plafond' | 'critere_documentaire' | 'qualitative';
  libelle: string;
  justification: string;
  seuil?: number;
  max?: number;
  categories?: string[];
  critere?: string;
}

export interface ProfilPython {
  id: string;
  nom: string;
  profil_risque: string;
  horizon_ans: [number, number | null];
  capital_fictif_cad: number;
  portefeuille: LigneSaisie[];
  pacte: { date_signature: string; regles: ReglePacte[] };
}

/** `detail_bareme` : quelle réponse a produit quelle règle, et ce qui reste à vérifier. */
export interface Bareme {
  date: string;
  /** Le seuil est resserré d'un cran si la personne vend quand ça baisse (vécu de 2022, sinon réaction). */
  resserrement: { resserre: boolean; cran: number; source: string | null; reponse_source: string | null };
  capacite: { plafond: number; decisifs: { question: string; reponse: string; plafond: number }[] } | null;
  seuil_retenu: { valeur: number; brut: number; resserre: boolean } | null;
  profil_risque: string;
  regles: { id: string; etiquette: 'fait' | 'hypothese'; reponses: Reponses; explication: string }[];
  controles: { statut: string; regle: string; message: string }[];
  limites: string[];
}

export interface Contradiction {
  id: string;
  questions: string[];
  message: string;
}

export interface ResultatPacte {
  profil: ProfilPython;
  bareme: Bareme;
  contradictions: Contradiction[];
}

export interface PacteSigne extends ResultatPacte {
  id: string;
  vues: VuesProfil;
}

/** La construction du Pacte n'est pas possible dans ce mode (démonstration, saisie libre). */
export class PacteNonDisponible extends Error {
  constructor() {
    super(
      "En démonstration, seul l'exemple préenregistré peut devenir un Pacte : le barème tourne en Python, "
      + 'sur la Lambda du Tribunal (mode direct). Utilisez « Remplir comme un profil de test », ou passez en mode direct.',
    );
    this.name = 'PacteNonDisponible';
  }
}

/** Réponses refusées par Python : un motif par problème. */
export class ReponsesRefusees extends Error {
  constructor(public readonly details: string[]) {
    super(details.join(' ; '));
    this.name = 'ReponsesRefusees';
  }
}

interface Demo {
  saisie: SaisiePacte;
  apercu: ResultatPacte;
  signe: PacteSigne;
}

const DEMO = questionnaire.demo as unknown as Demo;

export const QUESTIONS: Question[] = questionnaire.questions as Question[];

/** Réponses préenregistrées de l'exemple (étiquette Fictif), pour une démonstration reproductible. */
export function saisieDemo(): SaisiePacte {
  return structuredClone(DEMO.saisie);
}

/** Même saisie que l'exemple, sans tenir compte de l'ordre des clés ni des lignes vides. */
export function estSaisieDemo(saisie: SaisiePacte): boolean {
  const normaliser = (s: SaisiePacte) => JSON.stringify({
    nom: s.nom.trim(),
    capital: s.capital,
    portefeuille: s.portefeuille.filter((l) => l.poids > 0).map((l) => [l.ticker, Math.round(l.poids * 1e6)]),
    reponses: Object.keys(s.reponses).sort().map((k) => [k, s.reponses[k]]),
  });
  return normaliser(saisie) === normaliser(DEMO.saisie) && !Object.keys(saisie.modifications ?? {}).length;
}

async function envoyerProfil(saisie: SaisiePacte, apercu: boolean): Promise<Response> {
  if (!URL_API) throw new Error('Adresse du Tribunal absente : définissez VITE_API_URL (Function URL de la Lambda).');
  let reponse: Response;
  try {
    reponse = await fetch(`${URL_API}/profil`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ...saisie, apercu }),
    });
  } catch {
    throw new Error(
      'Le Tribunal est injoignable : réseau coupé, interface servie ailleurs que sur http://localhost:5173 (CORS), '
      + 'ou Lambda pas encore redéployée avec la route /profil.',
    );
  }
  if (reponse.status === 400) {
    const corps = await reponse.json().catch(() => null);
    if (corps && Array.isArray(corps.details)) throw new ReponsesRefusees(corps.details);
  }
  if (!reponse.ok) throw new Error(await lireErreur(reponse));
  return reponse;
}

/** Pacte que Python tire des réponses, sans rien ranger : pour l'aperçu avant signature. */
export async function apercuPacte(saisie: SaisiePacte): Promise<ResultatPacte> {
  if (!MODE_DIRECT) {
    if (!estSaisieDemo(saisie)) throw new PacteNonDisponible();
    return structuredClone(DEMO.apercu);
  }
  return (await envoyerProfil(saisie, true)).json() as Promise<ResultatPacte>;
}

/** Signe le Pacte : profil rangé (S3 en direct), puis disponible pour tous les écrans. */
export async function signerPacte(saisie: SaisiePacte): Promise<PacteSigne> {
  let signe: PacteSigne;
  if (!MODE_DIRECT) {
    if (!estSaisieDemo(saisie)) throw new PacteNonDisponible();
    signe = structuredClone(DEMO.signe);
  } else {
    signe = (await (await envoyerProfil(saisie, false)).json()) as PacteSigne;
  }
  enregistrerProfilCree({ profil: signe.vues.profil as Profil, calibrage: signe.vues.calibrage as DonneesCalibrage });
  return signe;
}
