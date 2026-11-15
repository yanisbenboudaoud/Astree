/**
 * Ce que les chiffres affichés ne disent pas : un seul catalogue pour tous les écrans.
 *
 * L'étude de cas demande de distinguer faits, hypothèses et scénarios fictifs, de présenter les
 * incertitudes importantes de façon compréhensible, d'expliquer chaque indicateur et ses limites
 * sur une période explicitée, et de rappeler que la volatilité n'est qu'un indicateur de risque
 * parmi d'autres (p. 17). Chaque phrase ici décrit une limite réelle de la méthode du projet
 * (CLAUDE.md, sections 6 et 6 bis) : aucune n'est générique ni rassurante.
 */
import { date } from '../lib/format';

/** Période d'analyse du jeu de données de départ (énoncé, p. 13). */
export const PERIODE = { debut: '2021-11-12', fin: '2026-11-12' };

export type Indicateur =
  | 'valeur' | 'rendement' | 'volatilite' | 'pire_baisse' | 'rendement_2022'
  | 'part_categories' | 'taille_max' | 'correlation' | 'recuperation' | 'seuil_pacte';

/** Ce que mesure un indicateur, et sa limite, en une phrase chacun (bulle ⓘ). */
export const INDICATEURS: Record<Indicateur, { mesure: string; limite: string }> = {
  valeur: {
    mesure: `Ce qu’aurait fait ce portefeuille fictif depuis le ${date(PERIODE.debut)}, en dollars canadiens.`,
    limite: 'Sans frais, sans impôts ni dépôt ou retrait en cours de route.',
  },
  rendement: {
    mesure: 'Gain moyen par an, intérêts composés, entre le premier et le dernier jour de la période.',
    limite: 'Il dépend beaucoup des dates de début et de fin : une autre période donnerait un autre chiffre.',
  },
  volatilite: {
    mesure: 'Ampleur des variations quotidiennes, ramenée à l’année.',
    limite: 'Elle ne dit ni dans quel sens le portefeuille bouge, ni la pire perte possible : c’est un indicateur de risque parmi d’autres.',
  },
  pire_baisse: {
    mesure: 'Plus forte chute depuis un sommet, mesurée jour après jour sur la période.',
    limite: 'Elle n’a été observée qu’une fois : une crise plus profonde reste possible.',
  },
  rendement_2022: {
    mesure: 'Résultat de la dernière séance de 2021 à la dernière de 2022, année où actions et obligations ont baissé ensemble.',
    limite: 'Une seule année de crise : la prochaine peut être différente.',
  },
  part_categories: {
    mesure: 'Poids des titres de ces catégories dans le portefeuille, une fois la décision appliquée.',
    limite: 'Les catégories sont tirées de la classe d’actif et du secteur du titre : un fonds diversifié compte d’un seul bloc.',
  },
  taille_max: {
    mesure: 'Plus grande taille qui respecte les règles calculables de votre Pacte, cherchée point par point.',
    limite: 'Elle vaut pour cette période seulement, et ne tient pas compte des règles qui ne se calculent pas.',
  },
  correlation: {
    mesure: 'À quel point deux titres ont varié ensemble, de −1 (en sens inverse) à 1 (ensemble).',
    limite: 'Ce lien change dans le temps et monte souvent pendant les crises, quand la diversification compte le plus.',
  },
  recuperation: {
    mesure: 'Temps pour retrouver le sommet après la pire chute.',
    limite: 'Observé une seule fois sur la période : il ne dit rien de la prochaine chute.',
  },
  seuil_pacte: {
    mesure: 'Limite que vous avez signée dans votre Pacte.',
    limite: 'Ce seuil est une hypothèse de l’équipe, pas une règle officielle, sauf s’il a été mesuré par le Pacte vécu.',
  },
};

export type Limite =
  | 'periode' | 'survivant' | 'simulation' | 'devises' | 'risque' | 'avenir'
  | 'seuils' | 'ia' | 'esg' | 'calibrage' | 'questionnaire' | 'apres_verdict';

/** Les limites de la méthode, titre et phrase (bloc « Ce que ces chiffres ne disent pas »). */
export const LIMITES: Record<Limite, { titre: string; texte: string }> = {
  periode: {
    titre: 'Une seule période de 5 ans',
    texte: `Du ${date(PERIODE.debut)} au ${date(PERIODE.fin)}, krach de 2022 et reprise compris. Une autre période donnerait d’autres chiffres.`,
  },
  survivant: {
    titre: 'Un passé un peu trop beau',
    texte: 'Les titres étudiés ont été choisis en 2026 : ceux qui ont disparu ou chuté n’y sont pas, ce qui embellit le passé.',
  },
  simulation: {
    titre: 'Des prix réels, un portefeuille simulé',
    texte: 'Les cours sont réels (Yahoo Finance, ajustés des dividendes) ; le portefeuille est rejoué, rééquilibré chaque jour, sans frais, impôts ni délai d’achat.',
  },
  devises: {
    titre: 'Tout est en dollars canadiens',
    texte: 'Les titres américains et la crypto sont convertis au taux de la Banque du Canada du jour (le dernier connu les jours fériés) : le change fait partie du résultat.',
  },
  risque: {
    titre: 'Le risque ne tient pas en un chiffre',
    texte: 'La volatilité et la pire baisse ne sont que deux mesures : votre horizon, la diversification et vos préférences comptent aussi.',
  },
  avenir: {
    titre: 'Le passé ne prédit pas l’avenir',
    texte: 'Ces chiffres décrivent ce qui s’est passé ; ils ne promettent rien pour la suite.',
  },
  seuils: {
    titre: 'Vos limites sont des hypothèses',
    texte: 'Les seuils du Pacte sont des choix de l’équipe, pas des règles officielles, sauf une pire baisse mesurée par le Pacte vécu.',
  },
  ia: {
    titre: 'Des arguments écrits par une IA, vérifiés par Python',
    texte: 'Le Procureur et l’Avocat sont des modèles de langage. Le Greffier vérifie chaque chiffre et l’absence de conseil, pas la justesse de leur raisonnement.',
  },
  esg: {
    titre: 'Des sources ESG limitées',
    texte: 'Le jeu de données n’a aucune donnée ESG : seuls quelques titres ont une fiche documentée par l’équipe. Sans source, le Greffier ne conclut pas.',
  },
  calibrage: {
    titre: 'De vraies baisses, une réaction imaginée',
    texte: 'Les jours de marché sont réels, mais répondre sur un écran n’est pas vivre la baisse avec son argent : votre limite mesurée reste une estimation.',
  },
  questionnaire: {
    titre: 'Un barème choisi par l’équipe',
    texte: 'La traduction de vos réponses en règles suit un barème d’hypothèses, pas une norme réglementaire. Vous pouvez modifier chaque seuil.',
  },
  apres_verdict: {
    titre: 'Rien après le 12 novembre 2026',
    texte: 'Les données s’arrêtent à cette date : ce qu’il advient d’une décision prise ensuite ne peut pas être mesuré ici.',
  },
};

export type Ecran = 'portefeuille' | 'decision' | 'tribunal' | 'verdict' | 'calibrage' | 'questionnaire';

/** Les limites qui touchent les chiffres de chaque écran, de la plus importante à la moins importante. */
export const LIMITES_PAR_ECRAN: Record<Ecran, Limite[]> = {
  portefeuille: ['periode', 'simulation', 'survivant', 'devises', 'avenir'],
  decision: ['simulation', 'periode', 'risque', 'survivant', 'seuils', 'avenir'],
  tribunal: ['ia', 'simulation', 'periode', 'survivant', 'esg', 'avenir'],
  verdict: ['seuils', 'periode', 'apres_verdict', 'avenir'],
  calibrage: ['calibrage', 'periode', 'avenir'],
  questionnaire: ['questionnaire', 'seuils'],
};
