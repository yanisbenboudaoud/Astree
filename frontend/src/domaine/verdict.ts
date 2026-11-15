/**
 * Options du Verdict (annexe C.6), déduites du procès et du Pacte, jamais d'un nom de profil.
 * L'outil ne recommande rien : il décrit chaque option avec les chiffres du dossier.
 */
import type { VerdictContrat } from '../api/contrat';
import type { DecisionUI, EntreeSimulation, Profil, ResultatTribunal, Statut, TablePosition } from '../api/types';
import { correlation, part, pourcent, seuil as seuilTexte } from '../lib/format';
import { entreePosition, libelleDecision } from './decision';
import { libelleCategories, pireStatut } from './pacte';

export type IdOption = 'maintenir' | 'ramener' | 'renoncer' | 'pacte';

export interface OptionVerdict {
  id: IdOption;
  verdict: VerdictContrat;
  titre: string;
  sousTitre: string;
  statut?: Statut;
  mesures: { libelle: string; valeur: string }[];
  /** Justification et case à cocher obligatoires avant de signer (annexe C.6). */
  engagement?: string;
  noteSiChoisie?: string;
  /** Taille ou part retenue par l'option « ramener », en points. */
  taille?: number;
}

export interface ContexteVerdict {
  profil: Profil;
  resultat: ResultatTribunal;
  decision: DecisionUI;
  table: TablePosition | null;
  entreeDecision: EntreeSimulation | null;
}

function controlesDuPacte(resultat: ResultatTribunal) {
  return resultat.controles.filter((c) => c.paragraphe !== undefined);
}

/** Statut d'une décision au regard du Pacte : les règles qualitatives (toujours à juger) ne comptent pas. */
export function statutDecision(profil: Profil, resultat: ResultatTribunal): Statut {
  const qualitatives = new Set(profil.pacte.regles.filter((r) => r.type === 'qualitative').map((r) => r.id));
  return pireStatut(controlesDuPacte(resultat).filter((c) => !qualitatives.has(c.regle)).map((c) => c.statut));
}

function phraseEngagement(profil: Profil, ctx: ContexteVerdict, idRegle: string): string {
  const regle = profil.pacte.regles.find((r) => r.id === idRegle);
  const apres = ctx.resultat.contrat.comparaison.apres;
  if (!regle) return 'une règle de mon Pacte est enfreinte';
  if (regle.type === 'pire_baisse_max') {
    return `la pire chute observée (${pourcent(apres.pire_baisse)}) dépasse ma limite de ${seuilTexte(regle.seuil ?? 0)}`;
  }
  if (regle.type === 'plafond') {
    const nom = libelleCategories(regle.categories ?? []).toLowerCase();
    const valeur = ctx.entreeDecision?.parts[regle.id];
    if (regle.max === 0) return `les ${nom} sont exclus par mon Pacte`;
    return valeur !== undefined
      ? `la part en ${nom} (${part(valeur)}) dépasse mon plafond de ${part(regle.max ?? 0)}`
      : `la part en ${nom} dépasse mon plafond de ${part(regle.max ?? 0)}`;
  }
  return `la règle « ${regle.libelle} » est enfreinte selon une pièce du dossier`;
}

export function optionsVerdict(ctx: ContexteVerdict): OptionVerdict[] {
  const { profil, resultat, decision } = ctx;
  const contrat = resultat.contrat;
  const violations = controlesDuPacte(resultat).filter((c) => c.statut === 'Violation');
  const statut = statutDecision(profil, resultat);
  const libelle = libelleDecision(decision);
  const panier = decision.type === 'panier';
  const apres = contrat.comparaison.apres;

  const mesuresMaintien = [
    { libelle: 'Chute max.', valeur: pourcent(apres.pire_baisse) },
    { libelle: 'Rendement', valeur: `${pourcent(apres.rendement_annuel, { signe: true })}/an` },
  ];
  if (panier && ctx.entreeDecision) {
    for (const regle of profil.pacte.regles.filter((r) => r.type === 'plafond' && r.max !== 0).slice(0, 1)) {
      mesuresMaintien.push({ libelle: libelleCategories(regle.categories ?? []), valeur: part(ctx.entreeDecision.parts[regle.id] ?? 0) });
    }
  }

  const paragraphes = violations.map((v) => `§${v.paragraphe}`).join(', ');
  const options: OptionVerdict[] = [{
    id: 'maintenir',
    verdict: 'maintenu',
    titre: panier ? 'Garder le panier tel quel' : `Maintenir ${libelle}`,
    sousTitre: violations.length === 0
      ? "Aucune règle mesurable de votre Pacte n'est enfreinte."
      : violations.length === 1
        ? `Vous passez outre la violation de votre Pacte (${paragraphes}).`
        : `Vous passez outre ${violations.length} violations de votre Pacte (${paragraphes}).`,
    statut,
    mesures: mesuresMaintien,
    engagement: violations.length
      ? `Je comprends que ${violations.map((v) => phraseEngagement(profil, ctx, v.regle)).join(' et que ')}, et que cette justification sera archivée.`
      : undefined,
  }];

  const demande = decision.type === 'position' ? decision.taille / 100 : 1;
  const tm = contrat.taille_max_compatible;
  if (tm !== null && tm > 0 && tm < demande - 1e-9) {
    const points = Math.round(tm * 100);
    const restantes = violations.filter((v) => {
      const regle = profil.pacte.regles.find((r) => r.id === v.regle);
      return regle && regle.type !== 'pire_baisse_max' && regle.type !== 'plafond';
    });
    const statutRamene: Statut = restantes.length ? 'Violation' : 'Conforme';
    if (decision.type === 'position' && ctx.table) {
      const entree = entreePosition(ctx.table, points);
      options.push({
        id: 'ramener',
        verdict: 'modifie',
        titre: `Ramener la position à ${points} %`,
        sousTitre: 'La plus grande taille compatible avec les règles mesurables de votre Pacte.',
        statut: statutRamene,
        mesures: [
          { libelle: 'Chute max.', valeur: pourcent(entree.chuteMax) },
          { libelle: 'Rendement', valeur: `${pourcent(entree.rendement, { signe: true })}/an` },
        ],
        taille: points,
      });
    } else if (panier) {
      const piece = contrat.pieces.find((p) => p.outil === 'taille_max_compatible');
      const v = piece?.valeurs ?? {};
      const mesures = typeof v.pire_baisse_a_taille_max === 'number' ? [{ libelle: 'Chute max.', valeur: pourcent(v.pire_baisse_a_taille_max) }] : [];
      for (const regle of profil.pacte.regles.filter((r) => r.type === 'plafond' && r.max !== 0).slice(0, 1)) {
        const valeur = v[`part_${(regle.categories ?? []).join('_')}_a_taille_max`];
        if (typeof valeur === 'number') mesures.push({ libelle: libelleCategories(regle.categories ?? []), valeur: pourcent(valeur) });
      }
      const corr = contrat.pieces.find((p) => p.outil === 'calculer_correlations');
      const paire = corr && Object.entries(corr.valeurs)
        .filter(([cle, val]) => cle.startsWith('correlation_') && typeof val === 'number')
        .sort((a, b) => (b[1] as number) - (a[1] as number))[0];
      options.push({
        id: 'ramener',
        verdict: 'modifie',
        titre: `Réallouer seulement ${points} %`,
        sousTitre: 'La plus grande part réallouable compatible avec les règles mesurables de votre Pacte ; le reste du portefeuille ne bouge pas.',
        statut: statutRamene,
        mesures,
        noteSiChoisie: paire
          ? `Calculée par le Tribunal (${piece?.id}). Les titres du panier restent corrélés : ${paire[0].slice(12).replace('_', '/')} à ${correlation(paire[1] as number)} (${corr!.id}), la poche se comporte presque comme un seul actif.`
          : undefined,
        taille: points,
      });
    }
  }

  options.push({
    id: 'renoncer',
    verdict: 'modifie',
    titre: panier ? 'Garder mon portefeuille actuel' : 'Renoncer',
    sousTitre: "Le portefeuille reste tel qu'il est.",
    mesures: [],
  });
  return options;
}

export const OPTION_PACTE: OptionVerdict = {
  id: 'pacte',
  verdict: 'pacte_ajuste',
  titre: 'Ajuster votre Pacte avant de décider',
  sousTitre: 'Le verdict archive votre intention ; la décision sera rejugée avec le Pacte modifié.',
  mesures: [],
};

export interface Archivage {
  resume: string;
  journal: string;
  statut: 'conforme' | 'violation' | 'a_verifier';
}

/** Bandeau de confirmation et entrée de journal après signature (annexe C.6). */
export function archivage(option: OptionVerdict, decision: DecisionUI, violations: number): Archivage {
  const libelle = libelleDecision(decision);
  const suffixe = ' · aucune transaction exécutée';
  const statut = option.statut === 'Violation' ? 'violation' : option.statut === 'À vérifier' ? 'a_verifier' : 'conforme';
  switch (option.id) {
    case 'maintenir':
      return {
        resume: `« ${libelle} » maintenu${violations ? ` malgré ${violations} violation${violations > 1 ? 's' : ''}` : ''}${suffixe}`,
        journal: decision.type === 'position' ? `Maintien de ${decision.ticker} à ${decision.taille} %` : `Maintien du ${libelle.toLowerCase()}`,
        statut,
      };
    case 'ramener':
      return decision.type === 'position'
        ? { resume: `Position ramenée à ${option.taille} % (simulation)${suffixe}`, journal: `${decision.ticker} ramené à ${option.taille} %`, statut }
        : { resume: `Réallocation limitée à ${option.taille} % (simulation)${suffixe}`, journal: `Panier réalloué à ${option.taille} %`, statut };
    case 'renoncer':
      return { resume: `« ${libelle} » abandonné${suffixe}`, journal: `Renonciation : ${libelle}`, statut: 'conforme' };
    default:
      return { resume: `« ${libelle} » en attente d'un Pacte ajusté${suffixe}`, journal: `En attente : ${libelle}`, statut: 'a_verifier' };
  }
}
