/**
 * Contrat du pipeline (CLAUDE.md, section 5) → types de l'écran Tribunal (annexe D.7).
 * Le même adaptateur sert aux procès enregistrés (mode démonstration) et au Tribunal en direct.
 */
import type { ContratTribunal, EtapeTraceContrat, EtiquetteContrat } from './contrat';
import type { Argument, ArgumentRejete, Controle, EtapeTrace, Piece, Provenance, ResultatTribunal } from './types';
import { paragraphe, parGravite, statutUi } from '../domaine/pacte';
import { part } from '../lib/format';

export function provenanceUi(etiquette: EtiquetteContrat): Provenance {
  if (etiquette === 'fait') return 'Fait';
  if (etiquette === 'hypothese') return 'Hypothèse';
  return 'Fictif';
}

const ROLES: Record<string, string> = {
  agent_profil: 'Agent Profil',
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
  else appel = `${outil}(${parametres(etape.entree)})`;

  const idPiece = typeof sortie === 'string' && ID_PIECE.test(sortie) ? sortie : undefined;
  if (etape.etape === 'orchestrateur' && !idPiece) etat = 'signalement';
  if (etape.raison && /d.office/i.test(etape.raison)) etat = 'signalement';

  return { role, appel, etat, raison: etape.raison, sortie: idPiece };
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
  for (const camp of ['Procureur', 'Avocat'] as const) {
    argumentsTribunal.filter((a) => a.camp === camp).forEach((a, i) => {
      for (const code of a.pieces) citations.set(code, [...(citations.get(code) ?? []), `${camp} · argument ${i + 1}`]);
    });
  }

  const pieces: Piece[] = contrat.pieces.map((p) => ({
    code: p.id,
    provenance: provenanceUi(p.etiquette),
    titre: p.titre,
    valeur: p.valeur_affichee,
    source: p.source,
    traitement: p.traitement,
    limites: p.limites,
    citeePar: citations.get(p.id) ?? [],
    origine: 'tribunal',
  }));

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
