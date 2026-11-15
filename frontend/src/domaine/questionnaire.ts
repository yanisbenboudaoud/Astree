/**
 * Logique d'affichage du questionnaire (#86), pure et testée. Elle ne calcule aucun chiffre
 * du Pacte : elle range les questions, dit si on peut avancer, et relit ce que Python
 * a renvoyé (barème, règles) pour l'afficher.
 */
import type { Bareme, LigneSaisie, Question, Reponses, ReglePacte, ValeurReponse } from '../api/questionnaire';

/** Tolérance d'arrondi sur le total des poids (ex. : 3 × 33,33 %). */
const TOLERANCE_TOTAL = 0.0005;

export interface Section {
  titre: string;
  /** Rang de la première question de la section. */
  debut: number;
  nombre: number;
}

/** Les sections dans l'ordre des questions (Horizon, Capacité, Tolérance, Expérience, Préférences). */
export function sections(questions: Question[]): Section[] {
  const resultat: Section[] = [];
  questions.forEach((q, i) => {
    const derniere = resultat[resultat.length - 1];
    if (derniere?.titre === q.section) derniere.nombre += 1;
    else resultat.push({ titre: q.section, debut: i, nombre: 1 });
  });
  return resultat;
}

export function estRepondue(valeur: ValeurReponse | undefined): boolean {
  if (valeur === undefined) return false;
  return Array.isArray(valeur) ? valeur.length > 0 : valeur.trim().length > 0;
}

/** Message qui empêche d'avancer, ou null. Une question facultative peut être passée. */
export function blocage(question: Question, valeur: ValeurReponse | undefined): string | null {
  if (question.obligatoire && !estRepondue(valeur)) return 'Cette question est obligatoire : choisissez une réponse pour continuer.';
  if (question.type === 'texte' && typeof valeur === 'string' && question.longueur_max && valeur.length > question.longueur_max) {
    return `${question.longueur_max} caractères au plus.`;
  }
  return null;
}

/** Choix multiples : « aucune » (ou « rien ») exclut les autres choix, et inversement. */
export function basculerChoixMultiple(courant: string[], id: string, exclusifs = ['aucune', 'rien']): string[] {
  if (courant.includes(id)) return courant.filter((c) => c !== id);
  if (exclusifs.includes(id)) return [id];
  return [...courant.filter((c) => !exclusifs.includes(c)), id];
}

/** Réponses envoyées à Python : sans les questions passées (Python le signale « à vérifier »). */
export function reponsesNettoyees(reponses: Reponses): Reponses {
  return Object.fromEntries(Object.entries(reponses)
    .filter(([, v]) => estRepondue(v))
    .map(([k, v]) => [k, typeof v === 'string' ? v.trim() : v]));
}

/** Questions passées, par leur nom court. */
export function questionsPassees(questions: Question[], reponses: Reponses): string[] {
  return questions.filter((q) => !estRepondue(reponses[q.id])).map((q) => q.nom_court);
}

/** Le libellé de la réponse donnée, tel que la question l'affiche. */
export function libelleReponse(question: Question, valeur: ValeurReponse): string {
  if (question.type === 'texte') return `« ${String(valeur)} »`;
  const options = question.type === 'cartes' ? question.cartes ?? [] : question.choix ?? [];
  const ids = Array.isArray(valeur) ? valeur : [valeur];
  return ids.map((id) => options.find((o) => o.id === id)?.libelle ?? id).join(', ');
}

/** « Parce que vous avez répondu » : chaque réponse qui a produit la règle, nom court et libellé. */
export function raisonsRegle(idRegle: string, bareme: Bareme, questions: Question[]): string[] {
  const detail = bareme.regles.find((r) => r.id === idRegle);
  if (!detail) return [];
  return Object.entries(detail.reponses).flatMap(([qid, valeur]) => {
    const question = questions.find((q) => q.id === qid);
    return question ? [`${question.nom_court} : ${libelleReponse(question, valeur)}`] : [];
  });
}

/** Une règle dont l'utilisateur peut choisir le seuil (Python applique le choix). */
export function seuilModifiable(regle: ReglePacte): { champ: 'seuil' | 'max'; valeur: number } | null {
  if (regle.type === 'pire_baisse_max' && regle.seuil !== undefined) return { champ: 'seuil', valeur: regle.seuil };
  if (regle.type === 'plafond' && regle.max !== undefined) return { champ: 'max', valeur: regle.max };
  return null;
}

/** Valeur saisie en points de pourcentage → valeur du Pacte (pire baisse négative, plafond positif). */
export function valeurDepuisPoints(regle: ReglePacte, points: number): number {
  const ratio = Math.round(Math.abs(points) * 10) / 1000;
  return regle.type === 'pire_baisse_max' ? -ratio : ratio;
}

export function totalPoids(lignes: LigneSaisie[]): number {
  return lignes.reduce((total, l) => total + (Number.isFinite(l.poids) ? l.poids : 0), 0);
}

/** Ce qui empêche d'envoyer le portefeuille, ou null : un titre au moins, sans doublon, total de 100 %. */
export function erreurPortefeuille(lignes: LigneSaisie[], capital: number): string | null {
  if (!Number.isFinite(capital) || capital <= 0) return 'Indiquez un capital fictif positif, en dollars canadiens.';
  const remplies = lignes.filter((l) => l.ticker);
  if (!remplies.length) return 'Ajoutez au moins un titre à votre portefeuille.';
  if (new Set(remplies.map((l) => l.ticker)).size !== remplies.length) return 'Chaque titre ne peut apparaître qu’une fois.';
  if (remplies.some((l) => !(l.poids > 0))) return 'Chaque titre doit avoir un poids supérieur à 0 %.';
  if (Math.abs(totalPoids(remplies) - 1) > TOLERANCE_TOTAL) return 'Les poids doivent totaliser 100 %.';
  return null;
}
