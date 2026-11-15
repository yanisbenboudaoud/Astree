/**
 * Questions suggérées du contre-interrogatoire (annexe D.6).
 * Les réponses sont produites par le Greffier, c'est-à-dire par du code sans LLM :
 * elles lisent les pièces du dossier ou les tables précalculées par le pipeline, et
 * tout nouveau calcul devient une nouvelle pièce numérotée. Aucun chiffre n'est inventé.
 */
import type { PieceContrat } from '../api/contrat';
import type { DecisionUI, Piece, Profil, Provenance, ResultatTribunal, TablePosition } from '../api/types';
import { correlation, part, pourcent, seuil as seuilTexte } from '../lib/format';
import { libelleCategories, paragraphe, seuilPireBaisse } from './pacte';
import { entreePosition } from './decision';

export interface QuestionSuggeree {
  id: string;
  libelle: string;
}

export interface Reponse {
  question: string;
  role: 'Greffier';
  provenance: Provenance;
  pieces: string[];
  texte: string;
  nouvellePiece?: Piece;
}

export interface ContexteQuestions {
  profil: Profil;
  resultat: ResultatTribunal;
  decision: DecisionUI;
  table: TablePosition | null;
  /** Pièces déjà au dossier, y compris celles créées par des questions précédentes. */
  pieces: Piece[];
}

const RACCOURCIS = [5, 15, 20, 25, 30, 40, 50];

function piece(resultat: ResultatTribunal, test: (p: PieceContrat) => boolean): PieceContrat | undefined {
  return resultat.contrat.pieces.find(test);
}

const simulation = (r: ResultatTribunal) => piece(r, (p) => p.outil === 'simuler_portefeuille' && 'pire_baisse' in p.valeurs);
const tailleMax = (r: ResultatTribunal) => piece(r, (p) => p.outil === 'taille_max_compatible');
const correlations = (r: ResultatTribunal) => piece(r, (p) => p.outil === 'calculer_correlations');
const documentaire = (r: ResultatTribunal) => piece(r, (p) => p.type === 'documentaire');

function tailleAlternative(decision: Extract<DecisionUI, { type: 'position' }>, maxConforme: number | null): number {
  const entre = RACCOURCIS.find((x) => x > (maxConforme ?? 0) && x < decision.taille && x !== maxConforme);
  if (entre !== undefined) return entre;
  return decision.taille * 2 <= 50 ? decision.taille * 2 : Math.max(1, Math.round(decision.taille / 2));
}

export function questionsSuggerees({ resultat, decision, table }: ContexteQuestions): QuestionSuggeree[] {
  const questions: QuestionSuggeree[] = [];
  if (decision.type === 'position' && table) {
    const max = table.maxConforme;
    const x = tailleAlternative(decision, max);
    questions.push({ id: `taille:${x}`, libelle: `Et à ${x} % ?` });
    if (max !== null && max > 0 && max < decision.taille) questions.push({ id: `taille:${max}`, libelle: `Pourquoi pas ${max} % ?` });
    else if (documentaire(resultat)) questions.push({ id: 'documentaire', libelle: 'Pourquoi le Greffier conclut-il ainsi sur vos valeurs ?' });
  }
  if (decision.type === 'panier') {
    if (correlations(resultat)) questions.push({ id: 'correlation', libelle: 'Pourquoi la corrélation compte-t-elle ?' });
    const valeurs = tailleMax(resultat)?.valeurs;
    if (typeof valeurs?.taille_max_compatible === 'number' && valeurs.taille_max_compatible < 1) {
      questions.push({ id: 'part', libelle: `Et si je ne réalloue que ${Math.round(valeurs.taille_max_compatible * 100)} % ?` });
    }
  }
  if (simulation(resultat)) questions.push({ id: 'fiabilite', libelle: 'Ces données sont-elles fiables ?' });
  return questions;
}

function prochainCode(pieces: Piece[]): string {
  const max = pieces.reduce((m, p) => Math.max(m, Number(p.code.slice(1)) || 0), 0);
  return `P${max + 1}`;
}

function premierePhrase(texte: string): string {
  const fin = texte.search(/[.;](\s|$)/);
  return (fin > 0 ? texte.slice(0, fin) : texte).trim();
}

export function repondre(question: QuestionSuggeree, contexte: ContexteQuestions): Reponse | null {
  const { profil, resultat, decision, table } = contexte;
  const base = { question: question.libelle, role: 'Greffier' as const };

  if (question.id.startsWith('taille:') && decision.type === 'position' && table) {
    const x = Number(question.id.slice(7));
    const entree = entreePosition(table, x);
    const seuil = seuilPireBaisse(profil);
    const regle = profil.pacte.regles.find((r) => r.type === 'pire_baisse_max');
    const sim = simulation(resultat);
    const code = prochainCode(contexte.pieces);
    let texte = `À ${x} %, la chute maximale observée serait de ${pourcent(entree.chuteMax)} et 2022 aurait donné ${pourcent(entree.rejeu2022, { signe: true })}.`;
    if (seuil !== undefined && regle) {
      texte += entree.statuts[regle.id] === 'violation'
        ? ` C'est au-delà de votre seuil de ${seuilTexte(seuil)} (Pacte §${paragraphe(profil.pacte.regles, regle.id)}).`
        : ` C'est dans la limite de ${seuilTexte(seuil)} de votre Pacte ; le rendement annualisé aurait été de ${pourcent(entree.rendement, { signe: true })}.`;
    }
    return {
      ...base,
      provenance: 'Fictif',
      pieces: [code],
      texte,
      nouvellePiece: {
        code,
        provenance: 'Fictif',
        titre: `Simulation à ${x} % (créée par une question)`,
        valeur: `${pourcent(entree.chuteMax)} max · 2022 : ${pourcent(entree.rejeu2022, { signe: true })}`,
        source: sim?.source,
        traitement: `Table précalculée par scripts/build_ui_series.py avec les fonctions du pipeline (simuler_portefeuille) : ${x} % en ${decision.ticker}, financement proportionnel, rééquilibrage quotidien, en CAD.`,
        limites: sim?.limites,
        citeePar: ['Greffier · réponse à une question'],
        origine: 'question',
      },
    };
  }

  if (question.id === 'documentaire') {
    const doc = documentaire(resultat);
    if (!doc) return null;
    const controle = resultat.controles.find((c) => c.pieces.includes(doc.id) && c.paragraphe !== undefined);
    const regle = profil.pacte.regles.find((r) => r.id === controle?.regle);
    const conclusion = controle?.statut === 'Violation' ? 'conclut à une violation' : controle?.statut === 'Conforme' ? 'conclut que la règle est respectée' : 'ne peut pas conclure';
    return {
      ...base,
      provenance: 'Fait',
      pieces: [doc.id],
      texte: `Votre Pacte pose la règle « ${regle?.libelle ?? controle?.regle} »${controle?.paragraphe ? ` (§${controle.paragraphe})` : ''}. La pièce ${doc.id} documente : ${doc.valeur_affichee}. Le Greffier ${conclusion} à partir de cette pièce seulement. ${premierePhrase(doc.limites)}.`,
    };
  }

  if (question.id === 'correlation') {
    const corr = correlations(resultat);
    if (!corr) return null;
    const paires = Object.entries(corr.valeurs)
      .filter(([cle, v]) => cle.startsWith('correlation_') && typeof v === 'number')
      .map(([cle, v]) => ({ noms: cle.slice(12).split('_'), valeur: v as number }))
      .sort((a, b) => b.valeur - a.valeur);
    if (!paires.length) return null;
    const [forte] = paires;
    return {
      ...base,
      provenance: 'Fait',
      pieces: [corr.id],
      texte: `${forte.noms[0]} et ${forte.noms[1]} sont corrélés à ${correlation(forte.valeur)} sur la période : deux actifs aussi corrélés montent et baissent presque ensemble, donc détenir les deux diversifie peu. ${premierePhrase(corr.limites)}.`,
    };
  }

  if (question.id === 'part') {
    const tm = tailleMax(resultat);
    const v = tm?.valeurs ?? {};
    if (!tm || typeof v.taille_max_compatible !== 'number' || typeof v.pire_baisse_a_taille_max !== 'number') return null;
    const parts = profil.pacte.regles
      .filter((r) => r.type === 'plafond' && typeof v[`part_${(r.categories ?? []).join('_')}_a_taille_max`] === 'number')
      .map((r) => `${libelleCategories(r.categories ?? []).toLowerCase()} à ${pourcent(v[`part_${(r.categories ?? []).join('_')}_a_taille_max`] as number)}`);
    return {
      ...base,
      provenance: 'Fictif',
      pieces: [tm.id],
      texte: `En ne réallouant que ${part(v.taille_max_compatible)} du portefeuille, la pire baisse simulée serait de ${pourcent(v.pire_baisse_a_taille_max)}${parts.length ? `, avec ${parts.join(' et ')}` : ''}. C'est la plus grande part compatible avec les règles mesurables de votre Pacte.`,
    };
  }

  if (question.id === 'fiabilite') {
    const sim = simulation(resultat);
    if (!sim) return null;
    return {
      ...base,
      provenance: 'Fait',
      pieces: [sim.id],
      texte: `Les prix viennent de ${sim.source}. Traitement : ${sim.traitement}. Limites : ${sim.limites}.`,
    };
  }
  return null;
}
