/**
 * Types consommés par les écrans (spec de l'interface, annexe D.7), plus les
 * données précalculées par scripts/build_ui_series.py. Les composants ne lisent
 * que ces types : brancher le vrai Tribunal ne demande de toucher que `api/`.
 */
import type { ContratTribunal, DecisionContrat, StatutContrat } from './contrat';

export type Provenance = 'Fait' | 'Hypothèse' | 'Fictif';
export type Statut = 'Violation' | 'À vérifier' | 'Conforme';

export interface Piece {
  code: string;
  provenance: Provenance;
  titre: string;
  valeur: string;
  source?: string;
  traitement?: string;
  limites?: string;
  citeePar?: string[];
  /** `question` : pièce créée par une réponse au contre-interrogatoire. */
  origine?: 'tribunal' | 'question';
}

export interface Argument {
  camp: 'Procureur' | 'Avocat';
  texte: string;
  provenance: Provenance;
  pieces: string[];
}

export interface Controle {
  statut: Statut;
  texte: string;
  pieces: string[];
  /** Identifiant de la règle du Pacte, ou d'un contrôle du système (verifier_chiffres…). */
  regle: string;
  /** Numéro de la règle dans le Pacte (§1, §2…), absent pour un contrôle du système. */
  paragraphe?: number;
}

export interface EtapeTrace {
  role: string;
  appel: string;
  etat: 'ok' | 'signalement';
  dureeMs?: number;
  raison?: string;
  sortie?: string;
}

export interface ArgumentRejete {
  camp: 'Procureur' | 'Avocat';
  texte: string;
  raison: string;
}

export interface ResultatTribunal {
  audience: string;
  titre: string;
  constat: string;
  controles: Controle[];
  arguments: Argument[];
  limiteAvocat?: string;
  pieces: Piece[];
  trace: EtapeTrace[];
  questionsSuggerees: string[];
  argumentsRejetes: ArgumentRejete[];
  procesId?: string;
  /** Contrat brut, pour le Verdict (taille maximale compatible, pièces de calcul). */
  contrat: ContratTribunal;
}

export interface SimulationDecision {
  taille?: number;
  panier?: { ticker: string; poids: number }[];
  chuteMax: number;
  rendement: number;
  volatilite: number;
  rejeu2022: number;
  serieReculActuel: [string, number][];
  serieReculDecision: [string, number][];
  seancesSousLimite?: { nombre: number; du: string; au: string };
}

// --- Données précalculées (frontend/src/data/generated) ---------------------------

export interface Calendrier {
  debut: string;
  fin: string;
  extraction: string;
  seances: number;
  semaines: string[];
  echelleRecul: number;
}

export interface DocumentTitre {
  critere: string;
  valeur: boolean | null;
  valeurAffichee: string;
  titre: string;
  source: string;
  dateConsultation: string;
}

export interface Indicateurs {
  rendement: number;
  volatilite: number;
  chuteMax: number;
  dateChuteMax: string;
  rejeu2022: number;
}

export interface Titre extends Indicateurs {
  ticker: string;
  nom: string;
  nomOriginal: string;
  classe: string;
  classeId: string;
  bourse: string;
  devise: string;
  secteur: string;
  groupe: string;
  categories: string[];
  anneesRecuperation: number | null;
  documents: DocumentTitre[];
}

export interface ReglePacte {
  id: string;
  type: 'pire_baisse_max' | 'plafond' | 'critere_documentaire' | 'qualitative';
  libelle: string;
  seuil?: number;
  categories?: string[];
  max?: number;
  critere?: string;
  statut: StatutContrat;
  message: string;
  valeur: number | null;
  utilisation: number | null;
}

export interface Profil {
  id: string;
  nom: string;
  age: number | null;
  metier: string | null;
  profilRisque: string;
  horizonAns: [number, number | null];
  capital: number;
  debut: string;
  fin: string;
  actuel: Indicateurs & {
    valeurChuteMax: number;
    valeurDepart: number;
    gain: number;
    gainPct: number;
    recul: string;
  };
  serieValeur: [string, number][];
  positions: { ticker: string; poids: number; valeur: number; groupe: string }[];
  groupes: { libelle: string; poids: number }[];
  pacte: { dateSignature: string; regles: ReglePacte[] };
  decisionDemo: DecisionContrat | null;
}

export interface SeancesSousLimite {
  nombre: number;
  du: string | null;
  au: string | null;
}

export interface EntreeSimulation extends Indicateurs {
  seances: SeancesSousLimite | null;
  statuts: Record<string, StatutContrat>;
  parts: Record<string, number>;
  compatible: boolean;
  /** Recul hebdomadaire encodé (voir lib/series.ts). */
  recul: string;
}

export interface TablePosition {
  profil: string;
  ticker: string;
  financement: string;
  maxConforme: number | null;
  tailles: (EntreeSimulation & { taille: number })[];
}

export interface TablePanier {
  profil: string;
  candidats: string[];
  pas: number;
  partReallouee: number;
  correlations: { a: string; b: string; valeur: number }[];
  compositions: Record<string, EntreeSimulation>;
}

export interface EntreeJournal {
  date: string;
  texte: string;
  statut: StatutContrat;
  nouveau?: boolean;
}

export interface ConfigProfilUI {
  decisionATester?: string;
  question?: string;
  recherche?: { mode: 'position' | 'panier'; titre: string; aide: string; placeholder: string };
  panierDemo?: string[];
  journal?: EntreeJournal[];
}

/** Décision en cours d'instruction, en points de pourcentage entiers. */
export type DecisionUI =
  | { type: 'position'; ticker: string; taille: number }
  | { type: 'panier'; lignes: { ticker: string; poids: number }[] };
