/**
 * Contrat du pipeline (CLAUDE.md, section 5) → types de l'écran Tribunal (annexe D.7).
 * Le même adaptateur sert aux procès enregistrés (mode démonstration) et au Tribunal en direct.
 */
import type { ContratTribunal, EchangeContrat, EtapeTraceContrat, EtiquetteContrat, PieceContrat } from './contrat';
import type { Argument, ArgumentRejete, Controle, Correction, Echange, EtapeTrace, Piece, Provenance, ResultatTribunal } from './types';
import { paragraphe, parGravite, statutUi } from '../domaine/pacte';
import { phaseDeLEtape } from '../domaine/progression';
import { part } from '../lib/format';

export function provenanceUi(etiquette: EtiquetteContrat): Provenance {
  if (etiquette === 'fait') return 'Fait';
  if (etiquette === 'hypothese') return 'Hypothèse';
  return 'Fictif';
}

const ROLES: Record<string, string> = {
  agent_profil: 'Agent Profil',
  calibrage: 'Pacte vécu',
  orchestrateur: 'Orchestrateur',
  procureur: 'Procureur',
  avocat: 'Avocat',
  greffier: 'Greffier',
};

const NOMS_PARAMETRES: Record<string, string> = { periode: 'période', part_reallouee: 'part réallouée', critere: 'critère' };

function valeurParametre(cle: string, valeur: unknown): string {
  if ((cle === 'taille' || cle === 'part_reallouee') && typeof valeur === 'number') return part(valeur);
  if (Array.isArray(valeur)) return valeur.map((v) => (typeof v === 'object' && v !== null && 'ticker' in v ? String((v as { ticker: string }).ticker) : String(v))).join(', ');
  return String(valeur);
}

function parametres(entree: unknown): string {
  if (entree === null || entree === undefined) return '';
  if (typeof entree !== 'object' || Array.isArray(entree)) return String(entree);
  return Object.entries(entree as Record<string, unknown>)
    .map(([cle, valeur]) => `${NOMS_PARAMETRES[cle] ?? cle}: ${valeurParametre(cle, valeur)}`)
    .join(', ');
}

const ID_PIECE = /^P\d+$/;

const VERIFICATIONS_GREFFIER: Record<string, string> = {
  verifier_pacte: 'Vérifier chaque règle de votre Pacte',
  verifier_chiffres: 'Vérifier chaque chiffre cité contre sa pièce',
  verifier_cadre_simulation: 'Vérifier qu’aucun argument ne conseille ni ne promet',
  'verifier_pacte+verifier_chiffres': 'Vérifier les règles du Pacte et chaque chiffre cité',
};

function arguments_(n: number | undefined): string {
  return n === undefined ? 'ses arguments' : `${n} argument${n > 1 ? 's' : ''}`;
}

/** Ce que fait une étape, en langage courant, à partir de son outil et de ses paramètres. */
function titreEtape(etape: EtapeTraceContrat, nombre: number | undefined, libelleDecision: string): string {
  const outil = etape.outil ?? '';
  const entree = (typeof etape.entree === 'object' && etape.entree !== null && !Array.isArray(etape.entree)
    ? etape.entree : {}) as Record<string, unknown>;
  const ticker = typeof entree.ticker === 'string' ? entree.ticker : undefined;
  const avec = ticker && typeof entree.taille === 'number' ? ` avec ${part(entree.taille)} en ${ticker}`
    : typeof entree.part_reallouee === 'number' ? ` avec ${part(entree.part_reallouee)} réallouée` : '';

  if (outil === 'bedrock' && etape.etape === 'procureur') return `Le Procureur plaide contre : ${arguments_(nombre)}`;
  if (outil === 'bedrock' && etape.etape === 'avocat') return `L’Avocat plaide pour : ${arguments_(nombre)}`;
  if (outil === 'bedrock') return 'Comprendre votre demande';
  if (outil === 'bedrock_correction') return 'Un argument renvoyé par le Greffier, puis corrigé';
  if (outil === 'valider_decision') return libelleDecision ? `Décision retenue : ${libelleDecision}` : 'Décision retenue';
  if (outil === 'charger_pacte') return 'Lire votre Pacte';
  if (etape.etape === 'calibrage') return 'Reprendre vos réponses au Pacte vécu';
  if (etape.etape === 'greffier') return VERIFICATIONS_GREFFIER[outil] ?? 'Contrôle du Greffier';
  switch (outil) {
    case 'simuler_portefeuille':
      return entree.periode === '2022' ? `Rejouer l’année 2022${avec}` : `Simuler votre portefeuille${avec}`;
    case 'indicateurs_actif':
      return ticker ? `Mesurer le risque de ${ticker} seul` : 'Mesurer le risque du titre';
    case 'calculer_correlations':
      return Array.isArray(entree.tickers) ? `Voir si ${entree.tickers.join(', ')} bougent ensemble` : 'Voir si les titres bougent ensemble';
    case 'taille_max_compatible':
      return ticker ? `Chercher la plus grande part de ${ticker} compatible avec votre Pacte` : 'Chercher la plus grande part compatible avec votre Pacte';
    case 'rechercher_documents':
      return ticker ? `Chercher des sources sur ${ticker}` : 'Chercher des sources';
    case 'consulter_jurisprudence':
      return 'Relire vos verdicts passés';
    case 'points_de_bascule':
      return 'Trouver ce qui changerait la réponse';
    default:
      return outil.replace(/_/g, ' ');
  }
}

export function etapeTrace(etape: EtapeTraceContrat): EtapeTrace {
  const role = ROLES[etape.etape] ?? etape.etape;
  const outil = etape.outil ?? '';
  const sortie = etape.sortie;
  const nombre = Array.isArray(sortie) ? sortie.length : undefined;
  let appel: string;
  let etat: EtapeTrace['etat'] = 'ok';

  if (outil === 'bedrock' && etape.etape === 'procureur') appel = `réquisitoire · ${nombre ?? '?'} arguments`;
  else if (outil === 'bedrock' && etape.etape === 'avocat') appel = `plaidoirie · ${nombre ?? '?'} arguments`;
  else if (outil === 'bedrock') appel = 'lecture de la demande (Bedrock) → décision structurée';
  else if (outil === 'bedrock_correction') {
    appel = 'argument renvoyé par le Greffier, puis corrigé';
    etat = 'signalement';
  } else if (outil === 'valider_decision') {
    const libelle = typeof sortie === 'object' && sortie !== null && 'libelle' in sortie ? String((sortie as { libelle: string }).libelle) : '';
    appel = `valider_decision → ${libelle}`;
  } else if (etape.etape === 'greffier') appel = `${outil} → ${String(sortie ?? '')}`;
  else if (etape.etape === 'calibrage') {
    const n = (etape.entree as { questions?: unknown[] } | undefined)?.questions?.length ?? 0;
    appel = `${outil} → ${n} réponses de l'utilisateur`;
  }
  else appel = `${outil}(${parametres(etape.entree)})`;

  const idPiece = typeof sortie === 'string' && ID_PIECE.test(sortie) ? sortie : undefined;
  const libelleDecision = outil === 'valider_decision' && typeof sortie === 'object' && sortie !== null && 'libelle' in sortie
    ? String((sortie as { libelle: string }).libelle) : '';
  let titre = titreEtape(etape, nombre, libelleDecision);
  if (etape.etape === 'orchestrateur' && !idPiece) {
    // Appel refusé ou en erreur : pas de pièce, la sortie donne le motif (« Erreur : … », #65).
    etat = 'signalement';
    if (typeof sortie === 'string' && sortie) appel = `${appel} → ${sortie}`;
    titre = `${titre} : refusé`;
  }
  if (etape.raison && /d.office/i.test(etape.raison)) etat = 'signalement';

  return { role, titre, appel, etat, phase: phaseDeLEtape(etape), raison: etape.raison, sortie: idPiece };
}

export function adapterPiece(p: PieceContrat, citeePar: string[] = []): Piece {
  return {
    code: p.id,
    provenance: provenanceUi(p.etiquette),
    titre: p.titre,
    valeur: p.valeur_affichee,
    source: p.source,
    traitement: p.traitement,
    limites: p.limites,
    citeePar,
    origine: 'tribunal',
  };
}

function argumentsEchange(echange: EchangeContrat): Argument[] {
  return [
    ...echange.requisitoire.map((a) => ({ camp: 'Procureur' as const, texte: a.texte, provenance: provenanceUi(a.etiquette), pieces: a.pieces })),
    ...echange.plaidoirie.map((a) => ({ camp: 'Avocat' as const, texte: a.texte, provenance: provenanceUi(a.etiquette), pieces: a.pieces })),
  ];
}

/** Échange du contre-interrogatoire (#55) → écran ; `pieces` : toutes les pièces du contrat (celles ajoutées y sont). */
export function adapterEchange(echange: EchangeContrat, pieces: PieceContrat[]): Echange {
  const args = argumentsEchange(echange);
  const ajoutees = pieces.filter((p) => echange.pieces_ajoutees.includes(p.id)).map((p) => {
    const citeePar = (['Procureur', 'Avocat'] as const).flatMap((camp) => args
      .filter((a) => a.camp === camp)
      .flatMap((a, i) => (a.pieces.includes(p.id) ? [`${camp} · réponse ${i + 1}`] : [])));
    return adapterPiece(p, citeePar);
  });
  return {
    question: echange.question,
    arguments: args,
    piecesAjoutees: ajoutees,
    controle: echange.controle_chiffres.message,
    argumentsRejetes: echange.arguments_rejetes.map((a) => ({ camp: a.cote === 'requisitoire' ? 'Procureur' : 'Avocat', texte: a.texte, raison: a.raison })),
  };
}

export interface ContexteAdaptation {
  nomProfil: string;
  titreDecision: string;
  audience: string;
  procesId?: string;
}

export function adapterContrat(contrat: ContratTribunal, contexte: ContexteAdaptation): ResultatTribunal {
  const regles = contrat.pacte.regles;

  const argumentsTribunal: Argument[] = [
    ...contrat.requisitoire.map((a) => ({ camp: 'Procureur' as const, texte: a.texte, provenance: provenanceUi(a.etiquette), pieces: a.pieces })),
    ...contrat.plaidoirie.map((a) => ({ camp: 'Avocat' as const, texte: a.texte, provenance: provenanceUi(a.etiquette), pieces: a.pieces })),
  ];

  const citations = new Map<string, string[]>();
  const citer = (args: Argument[], libelle: (camp: string, i: number) => string) => {
    for (const camp of ['Procureur', 'Avocat'] as const) {
      args.filter((a) => a.camp === camp).forEach((a, i) => {
        for (const code of a.pieces) citations.set(code, [...(citations.get(code) ?? []), libelle(camp, i)]);
      });
    }
  };
  citer(argumentsTribunal, (camp, i) => `${camp} · argument ${i + 1}`);
  const echangesContrat = contrat.contre_interrogatoire ?? [];
  echangesContrat.forEach((e, n) => citer(argumentsEchange(e), (camp, i) => `${camp} · question ${n + 1}, réponse ${i + 1}`));

  const pieces: Piece[] = contrat.pieces.map((p) => adapterPiece(p, citations.get(p.id) ?? []));

  const controles: Controle[] = parGravite(contrat.controles.map((c) => {
    const numero = paragraphe(regles, c.regle);
    return {
      statut: statutUi(c.statut),
      texte: numero ? `${c.message} (Pacte §${numero})` : c.message,
      pieces: c.pieces ?? [],
      regle: c.regle,
      paragraphe: numero,
    };
  }));

  const duPacte = controles.filter((c) => c.paragraphe !== undefined);
  const principal = duPacte.find((c) => c.statut === 'Violation') ?? duPacte.find((c) => c.statut === 'À vérifier' && !/non mesurable/i.test(c.texte));
  const constat = principal ? `${principal.texte}.` : "Aucune règle mesurable de votre Pacte n'est enfreinte.";

  const corrections: Correction[] = contrat.trace.flatMap((e) => {
    if (e.outil !== 'bedrock_correction') return [];
    const entree = (e.entree ?? {}) as { argument?: unknown; motif?: unknown };
    const sortie = (e.sortie ?? {}) as { texte?: unknown };
    if (typeof entree.argument !== 'string' || typeof entree.motif !== 'string' || typeof sortie.texte !== 'string') return [];
    return [{ camp: e.etape === 'procureur' ? 'Procureur' as const : 'Avocat' as const, original: entree.argument, motif: entree.motif, corrige: sortie.texte }];
  });

  const argumentsRejetes: ArgumentRejete[] = contrat.arguments_rejetes.map((a) => ({
    camp: a.cote === 'requisitoire' ? 'Procureur' : 'Avocat',
    texte: a.texte,
    raison: a.raison,
  }));

  return {
    audience: contexte.audience,
    titre: `${contexte.nomProfil} c. « ${contexte.titreDecision} »`,
    constat,
    controles,
    arguments: argumentsTribunal,
    limiteAvocat: contrat.controles.find((c) => c.regle === 'biais_survivant')?.message,
    pieces,
    trace: contrat.trace.map(etapeTrace),
    questionsSuggerees: [],
    argumentsRejetes,
    corrections,
    echanges: echangesContrat.map((e) => adapterEchange(e, contrat.pieces)),
    procesId: contexte.procesId,
    contrat,
  };
}

/** Numéro d'audience affiché, tiré de l'identifiant du procès archivé dans S3 (« 2026-11-14-3f9a0c1b2d4e »). */
export function numeroAudience(procesId: string | null | undefined): string {
  if (!procesId) return '—';
  const hex = procesId.replace(/[^0-9a-f]/gi, '').slice(-4) || '0';
  return String(parseInt(hex, 16) % 10000).padStart(4, '0');
}
