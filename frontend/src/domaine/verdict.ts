/**
 * Options du Verdict (annexe C.6), déduites du procès et du Pacte, jamais d'un nom de profil.
 * L'outil ne recommande rien : il décrit chaque option avec les chiffres du dossier.
 */
import type { VerdictContrat } from '../api/contrat';
import type { DecisionUI, EntreeSimulation, Profil, ResultatTribunal, Statut, TablePosition } from '../api/types';
import { correlation, part, pourcent, seuil as seuilTexte } from '../lib/format';
import { entreePosition, libelleDecision } from './decision';
import { libelleCategories, paragraphe, pireStatut } from './pacte';

export type IdOption = 'maintenir' | 'ramener' | 'renoncer' | 'pacte';

export interface OptionVerdict {
  id: IdOption;
  verdict: VerdictContrat;
  titre: string;
  sousTitre: string;
  statut?: Statut;
  mesures: { libelle: string; valeur: string }[];
  /** Pire baisse simulée de l'option (brute), pour la placer face au seuil du Pacte. */
  pireBaisse?: number;
  /** Seuil de pire baisse qui s'appliquerait avec cette option (le seuil ajusté pour « pacte »). */
  seuil?: number;
  /** Seuil actuel du Pacte, quand l'option le change. */
  ancienSeuil?: number;
  /** Option « pacte » : les règles à changer pour que la décision soit conforme (#61). */
  ajustements?: { regle: string; texte: string; pieces: string[] }[];
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
    return `la pire baisse observée (${pourcent(apres.pire_baisse)}) dépasse ma limite de ${seuilTexte(regle.seuil ?? 0)}`;
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
  const actuel = contrat.comparaison.actuel;
  const seuil = contrat.pacte.regles.find((r) => r.type === 'pire_baisse_max')?.seuil;

  const mesuresMaintien = [
    { libelle: 'Pire baisse', valeur: pourcent(apres.pire_baisse) },
    { libelle: 'Rendement', valeur: `${pourcent(apres.rendement_annuel, { signe: true })}/an` },
  ];
  if (panier && ctx.entreeDecision) {
    for (const regle of profil.pacte.regles.filter((r) => r.type === 'plafond' && r.max !== 0).slice(0, 1)) {
      mesuresMaintien.push({ libelle: libelleCategories(regle.categories ?? []), valeur: part(ctx.entreeDecision.parts[regle.id] ?? 0) });
    }
  }

  const options: OptionVerdict[] = [{
    id: 'maintenir',
    verdict: 'maintenu',
    titre: panier ? 'Garder le panier tel quel' : `Maintenir ${libelle}`,
    sousTitre: 'La décision telle que jugée par le Tribunal.',
    statut,
    mesures: mesuresMaintien,
    pireBaisse: apres.pire_baisse,
    seuil,
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
        sousTitre: 'La plus grande taille compatible avec les règles chiffrées de votre Pacte.',
        statut: statutRamene,
        mesures: [
          { libelle: 'Pire baisse', valeur: pourcent(entree.chuteMax) },
          { libelle: 'Rendement', valeur: `${pourcent(entree.rendement, { signe: true })}/an` },
        ],
        pireBaisse: entree.chuteMax,
        seuil,
        taille: points,
      });
    } else if (panier) {
      const piece = contrat.pieces.find((p) => p.outil === 'taille_max_compatible');
      const v = piece?.valeurs ?? {};
      const pireBaisse = typeof v.pire_baisse_a_taille_max === 'number' ? v.pire_baisse_a_taille_max : undefined;
      const mesures = pireBaisse !== undefined ? [{ libelle: 'Pire baisse', valeur: pourcent(pireBaisse) }] : [];
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
        sousTitre: 'La plus grande part compatible avec les règles chiffrées de votre Pacte ; le reste ne bouge pas.',
        statut: statutRamene,
        mesures,
        pireBaisse,
        seuil,
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
    sousTitre: 'Votre portefeuille actuel, sans la décision.',
    // Taille compatible connue : à 0 %, les règles chiffrées sont respectées ; null : même 0 % les viole.
    statut: tm === null ? 'Violation' : 'Conforme',
    mesures: [
      { libelle: 'Pire baisse', valeur: pourcent(actuel.pire_baisse) },
      { libelle: 'Rendement', valeur: `${pourcent(actuel.rendement_annuel, { signe: true })}/an` },
    ],
    pireBaisse: actuel.pire_baisse,
    seuil,
  });

  options.push(optionPacte(ctx, mesuresMaintien, seuil));
  return options;
}

/**
 * « Ajuster mon Pacte » (verdict `pacte_ajuste`) : garder la décision et changer la règle.
 * Les nouveaux seuils sont ceux des points de bascule (#61), calculés par Python.
 */
function optionPacte(ctx: ContexteVerdict, mesures: OptionVerdict['mesures'], seuil: number | undefined): OptionVerdict {
  const { profil, resultat } = ctx;
  const regles = resultat.contrat.pacte.regles;
  const bascules = resultat.contrat.points_de_bascule ?? [];
  const ajustements = bascules.map((p) => {
    const regle = regles.find((r) => r.id === p.regle);
    const numero = paragraphe(regles, p.regle);
    const nom = p.type === 'pire_baisse_max' ? 'Pire baisse tolérée' : `Plafond ${libelleCategories(regle?.categories ?? []).toLowerCase()}`;
    const avant = p.type === 'pire_baisse_max' ? seuilTexte(p.seuil_actuel) : part(p.seuil_actuel);
    const apres = p.type === 'pire_baisse_max' ? pourcent(p.seuil_suffisant) : part(p.seuil_suffisant);
    return { regle: p.regle, texte: `${numero ? `§${numero} · ` : ''}${nom} : ${apres} au lieu de ${avant}`, pieces: p.pieces };
  });
  const violations = controlesDuPacte(resultat).filter((c) => c.statut === 'Violation');
  const couvertes = new Set(bascules.map((p) => p.regle));
  const restantes = violations.filter((v) => !couvertes.has(v.regle));
  const baisse = bascules.find((p) => p.type === 'pire_baisse_max');
  return {
    id: 'pacte',
    verdict: 'pacte_ajuste',
    titre: 'Ajuster mon Pacte',
    sousTitre: ajustements.length
      ? 'Garder la décision et changer la règle. La décision serait conforme avec :'
      : 'Garder la décision et modifier une règle de votre Pacte.',
    statut: violations.length === 0 ? statutDecision(profil, resultat) : restantes.length ? 'Violation' : 'Conforme',
    mesures,
    pireBaisse: resultat.contrat.comparaison.apres.pire_baisse,
    seuil: baisse ? baisse.seuil_suffisant : seuil,
    ancienSeuil: baisse ? baisse.seuil_actuel : undefined,
    ajustements,
    noteSiChoisie: 'Le verdict archive votre intention ; la décision sera rejugée avec le Pacte modifié.',
  };
}

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

export interface PointDeBascule {
  regle: string;
  /** Numéro de la règle dans le Pacte (§1, §2…). */
  paragraphe?: number;
  libelle: string;
  /** « Conforme jusqu'à 9 % en TSLA, ou avec un seuil de −29,0 % au lieu de −12,0 % » (écrit par Python). */
  message: string;
  pieces: string[];
}

/** « Qu'est-ce qui changerait la réponse ? » (#61) : un point par règle calculable en violation, lu dans le contrat. */
export function pointsDeBascule(resultat: ResultatTribunal): PointDeBascule[] {
  const regles = resultat.contrat.pacte.regles;
  return (resultat.contrat.points_de_bascule ?? []).map((p) => ({
    regle: p.regle,
    paragraphe: paragraphe(regles, p.regle),
    libelle: regles.find((r) => r.id === p.regle)?.libelle ?? p.regle,
    message: p.message,
    pieces: p.pieces,
  }));
}
