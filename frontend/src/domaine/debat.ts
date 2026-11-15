/**
 * Le débat point par point : chaque argument est rangé sous une question, pour mettre face à
 * face ce que disent le Procureur et l'Avocat sur le même sujet. Le sujet est lu dans la
 * première phrase de l'argument (sa conclusion, consignes de pipeline/debat.py), par des
 * règles fixes : rien n'est calculé ni réécrit, le texte des agents reste intact.
 */
import type { Argument } from '../api/types';

/**
 * Première phrase d'un argument, pour la ligne repliée. Une phrase finit sur « . », « ! » ou « ? »
 * suivi d'une majuscule : « déc. 2021 » ou « −15,1 % » ne coupent pas.
 */
export function accroche(texte: string): { tete: string; suite: string } {
  const fin = texte.search(/[.!?»](?=\s+[A-ZÀÂÉÈÊÎÔÛÇ«])/);
  if (fin < 0) return { tete: texte, suite: '' };
  return { tete: texte.slice(0, fin + 1), suite: texte.slice(fin + 1).trim() };
}

export type Theme =
  | 'titre_seul' | 'reactions' | 'antecedents' | 'valeurs' | 'annee_2022' | 'taille'
  | 'diversification' | 'regles' | 'rendement' | 'perte' | 'autre';

/** Question affichée au-dessus de chaque point, dans l'ordre où les règles sont essayées. */
export const QUESTIONS: Record<Theme, string> = {
  titre_seul: 'Et le titre, pris seul ?',
  reactions: 'Qu’avez-vous répondu face à de vraies baisses ?',
  antecedents: 'Avez-vous déjà tranché ce conflit ?',
  valeurs: 'La décision respecte-t-elle vos valeurs ?',
  annee_2022: 'Et dans une année de crise comme 2022 ?',
  taille: 'Une taille plus modeste passerait-elle ?',
  diversification: 'Les titres bougent-ils ensemble ?',
  regles: 'Et les autres règles de votre Pacte ?',
  rendement: 'Qu’est-ce que la décision aurait rapporté ?',
  perte: 'Combien pourriez-vous perdre au pire moment ?',
  autre: 'Autres points',
};

/** Nom court de chaque point, pour le sommaire du débat. */
export const LIBELLES_COURTS: Record<Theme, string> = {
  titre_seul: 'Le titre seul',
  reactions: 'Vos réactions',
  antecedents: 'Antécédents',
  valeurs: 'Vos valeurs',
  annee_2022: 'Crise de 2022',
  taille: 'Taille modeste',
  diversification: 'Diversification',
  regles: 'Autres règles',
  rendement: 'Rendement',
  perte: 'Pire moment',
  autre: 'Autres points',
};

/** Règles essayées dans cet ordre : la plus précise d'abord (« XOM seule » avant « chute »). */
const REGLES: [Theme, RegExp][] = [
  // Sensible à la casse : « XOM seule » est un symbole, « d'un seul bloc » ne l'est pas.
  ['titre_seul', /\b[Pp]ris(e)? seul|\b[A-Z][A-Z.-]+ seule?\b|revenue? à (ce|son) sommet|retrouvé (ce|son) sommet/],
  ['reactions', /vous avez répondu|jours? de marché|rejeu d.une chute|revécu/i],
  ['antecedents', /procès|déjà (été )?jugé|antécédent/i],
  ['valeurs', /controvers|poursuite|valeurs|ESG|climat/i],
  ['annee_2022', /2022/],
  ['taille', /jusqu.à \d|plus modeste|respecterait|serait respectée|au maximum respecte|(position|taille) de \d|\bà \d+(,\d+)?\s%\sen [A-Z]/i],
  ['diversification', /ensemble|corrélation|\blien\b|\bliés\b|moteur|d.un seul bloc/i],
  ['regles', /crypto|\btech\b|règles calculables|seule la règle|équilibre|stabilité|votre Pacte (demande|prévoit|dit|pose)/i],
  ['rendement', /par an|rendement/i],
  ['perte', /pire moment|chute|pire baisse|perdu/i],
];

export function themeArgument(texte: string): Theme {
  const { tete } = accroche(texte);
  return REGLES.find(([, regle]) => regle.test(tete))?.[0] ?? 'autre';
}

export interface ArgumentNumerote {
  argument: Argument;
  /** Rang dans son camp (1, 2…), comme dans « Procureur · argument 2 » des pièces. */
  numero: number;
}

export interface PointDebat {
  theme: Theme;
  question: string;
  procureur: ArgumentNumerote[];
  avocat: ArgumentNumerote[];
}

/**
 * Points du débat, dans l'ordre où ils apparaissent : d'abord ceux du Procureur (du plus fort
 * au plus faible), puis ceux que seul l'Avocat soulève. « Autres points » reste en dernier.
 */
export function regrouperDebat(procureur: Argument[], avocat: Argument[]): PointDebat[] {
  const points = new Map<Theme, PointDebat>();
  const ranger = (args: Argument[], camp: 'procureur' | 'avocat') => args.forEach((argument, i) => {
    const theme = themeArgument(argument.texte);
    if (!points.has(theme)) points.set(theme, { theme, question: QUESTIONS[theme], procureur: [], avocat: [] });
    points.get(theme)![camp].push({ argument, numero: i + 1 });
  });
  ranger(procureur, 'procureur');
  ranger(avocat, 'avocat');
  const liste = [...points.values()];
  return [...liste.filter((p) => p.theme !== 'autre'), ...liste.filter((p) => p.theme === 'autre')];
}
