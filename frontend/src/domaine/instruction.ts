/**
 * Comment les agents ont instruit le dossier (#189) : les calculs choisis par l'orchestrateur
 * (Bedrock) et ceux ajoutés d'office par Python, puis la mesure des appels Bedrock du procès.
 * Rien n'est calculé ici : tout vient de la trace et du champ `bedrock` du contrat.
 */
import type { BedrockContrat } from '../api/contrat';
import type { EtapeTrace } from '../api/types';
import { compte, nombre } from '../lib/format';

export interface ChoixInstruction {
  titre: string;
  /** `orchestrateur` : choisi par le modèle ; `office` : ajouté par Python ; `refuse` : appel refusé, sans pièce. */
  origine: 'orchestrateur' | 'office' | 'refuse';
  raison?: string;
  piece?: string;
}

/** Les appels d'outils de la phase de l'orchestrateur, dans l'ordre, avec qui les a décidés. */
export function choixInstruction(trace: EtapeTrace[]): ChoixInstruction[] {
  return trace.filter((e) => e.phase === 'orchestrateur').map((e) => {
    const office = Boolean(e.raison && /d.office/i.test(e.raison));
    const origine = !e.sortie ? 'refuse' : office ? 'office' : 'orchestrateur';
    return { titre: e.titre, origine, raison: e.raison, piece: e.sortie };
  });
}

const AGENTS: Record<string, string> = {
  agent_profil: 'Agent Profil',
  orchestrateur: 'Orchestrateur',
  procureur: 'Procureur',
  avocat: 'Avocat',
};

/**
 * La mesure du procès en phrases courtes : appels par agent, jetons, coût estimé, durée,
 * Guardrail. Le coût est une estimation au tarif public (hypothèse écrite par Python).
 */
export function resumeBedrock(bedrock: BedrockContrat): string[] {
  const parAgent = bedrock.par_agent
    .map((a) => `${AGENTS[a.agent] ?? a.agent} ${a.appels}`)
    .join(', ');
  const lignes = [
    `${compte(bedrock.appels, 'appel')} à Amazon Bedrock${parAgent ? ` (${parAgent})` : ''}`,
    `${nombre(bedrock.jetons_entree)} jetons lus, ${nombre(bedrock.jetons_sortie)} écrits · environ ${nombre(bedrock.cout_estime_usd, 2)} $ US au tarif public`,
    `Procès complet en ${nombre(bedrock.duree_proces_s, 0)} s · le modèle a travaillé ${nombre(bedrock.duree_bedrock_s, 0)} s au total (appels en parallèle additionnés)`,
  ];
  if (bedrock.garde_fou) {
    const { verifications, interventions } = bedrock.garde_fou;
    lignes.push(`Guardrail Bedrock : ${compte(verifications, 'texte contrôlé', 'textes contrôlés')}, ${compte(interventions, 'intervention')}`);
  }
  return lignes;
}

/** « +12,4 s » : moment d'une étape depuis le début du procès. */
export function moment(secondes: number): string {
  return `+${nombre(secondes, 1)} s`;
}
