/**
 * Types consommés par les écrans (spec de l'interface, annexe D.7), plus les
 * données précalculées par scripts/build_ui_series.py. Les composants ne lisent
 * que ces types : brancher le vrai Tribunal ne demande de toucher que `api/`.
 */
import type { ContratTribunal, DecisionContrat, StatutContrat } from './contrat';
import type { PhaseProces } from '../domaine/progression';

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
  /** Ce que fait l'étape, en langage courant (« Simuler votre portefeuille avec 10 % en XOM »). */
  titre: string;
  /** L'appel technique tel que tracé (outil et paramètres), montré dans le détail technique. */
  appel: string;
  etat: 'ok' | 'signalement';
  /** Phase du procès où l'étape a lieu (#90). */
  phase: PhaseProces;
  dureeMs?: number;
  raison?: string;
  sortie?: string;
}

/** Progression réelle d'un procès en direct (#90), relue sur la Lambda pendant l'attente. */
export interface ProgressionTribunal {
  /** Phase en cours ; null tant que le procès accepté n'a pas commencé. */
  phase: PhaseProces | null;
  /** Étapes déjà faites, dans l'ordre où elles ont eu lieu. */
  etapes: EtapeTrace[];
  /** Ce que le Tribunal fait en ce moment (« Argument renvoyé au Procureur… »). */
  activite?: string;
  /** Message sur le suivi lui-même (Tribunal occupé, réseau) : la relecture continue. */
  avis?: string;
}

export interface ArgumentRejete {
  camp: 'Procureur' | 'Avocat';
  texte: string;
  raison: string;
}

/** Réponse de `POST /verifier` (« Trompez le Greffier », #69), nombre par nombre. */
export interface ResultatVerification {
  valide: boolean;
  motif: string | null;
  nombres: { texte: string; trouve: boolean; sources: string[]; motif: string | null }[];
  compte: string;
  dureeMs: number;
}

/** Argument renvoyé par le Greffier à son agent pendant le procès, puis corrigé (trace `bedrock_correction`). */
export interface Correction {
  camp: 'Procureur' | 'Avocat';
  original: string;
  motif: string;
  corrige: string;
}

/** Échange du contre-interrogatoire (#55), prêt à afficher. */
export interface Echange {
  question: string;
  arguments: Argument[];
  piecesAjoutees: Piece[];
  controle: string;
  argumentsRejetes: ArgumentRejete[];
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
  corrections: Correction[];
  /** Questions libres déjà posées sur ce procès (contrat relu dans S3). */
  echanges: Echange[];
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
  /** Seuil mesuré par le Pacte vécu (#68) : « Mesurée sur vos réponses du … ». */
  provenance?: string;
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

export interface ConfigRecherche {
  mode: 'position' | 'panier';
  titre: string;
  aide: string;
  placeholder: string;
}

export interface ConfigProfilUI {
  decisionATester?: string;
  question?: string;
  recherche?: ConfigRecherche;
  panierDemo?: string[];
  journal?: EntreeJournal[];
}

// --- Pacte vécu (#68) : frontend/src/data/generated/calibrage/<id>.json ----------

export interface QuestionBaisse {
  id: string;
  type: 'baisse';
  choix: string[];
  serie: string;
  date_sommet: string;
  date_jour: string;
  baisse: number;
  valeur_sommet: number;
  valeur_jour: number;
  niveau: number;
  anneesRetour: number | null;
  /** Valeur en dollars (capital au sommet) jusqu'au jour de l'épisode : rien de la suite. */
  historique: [string, number][];
}

export interface QuestionCapacite {
  id: 'capacite';
  type: 'capacite';
  choix: string[];
  serie: string;
  date_sommet: string;
  baisse: number;
  annees_retour: number | null;
  horizon_ans: (number | null)[];
}

export interface QuestionCrypto {
  id: 'crypto';
  type: 'crypto';
  choix: string[];
  serie: string;
  date_sommet: string;
  date_jour: string;
  baisse: number;
  part: number;
  valeur_sommet: number;
  valeur_jour: number;
}

export interface QuestionValeurs {
  id: string;
  type: 'valeurs';
  choix: string[];
  regle: string;
  libelle: string;
}

export type QuestionCalibrage = QuestionBaisse | QuestionCapacite | QuestionCrypto | QuestionValeurs;

export interface DonneesCalibrage {
  profil: string;
  capital: number;
  horizonAns: (number | null)[];
  episodes: QuestionBaisse[];
  crypto: QuestionCrypto | null;
  valeurs: QuestionValeurs[];
  /** Réponses préenregistrées du profil de test (étiquette fictif) et le seuil calculé en Python. */
  demo: { date: string; reponses: Record<string, string>; seuil: number | null } | null;
  source: string;
  limites: string;
}

/** Décision en cours d'instruction, en points de pourcentage entiers. */
export type DecisionUI =
  | { type: 'position'; ticker: string; taille: number }
  | { type: 'panier'; lignes: { ticker: string; poids: number }[] };
