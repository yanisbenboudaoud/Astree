/**
 * Agents coordonnés et mesurés (#189) : répliques, instruction du dossier, mesure Bedrock et
 * moment de chaque étape, sur un vrai procès enregistré complété comme le fait le pipeline.
 */
import contratRobert from '../data/proces/2026-11-15-fcb6ce39f184.json';
import type { BedrockContrat, ContratTribunal } from '../api/contrat';
import { adapterContrat } from '../api/adaptateur';
import { jugerDecision, reponsesDuContrat } from '../api/tribunal';
import robertVecu from '../data/proces/2026-11-16-2e2faa67372b.json';
import { choixInstruction, moment, resumeBedrock } from '../domaine/instruction';
import { phaseDeLEtape } from '../domaine/progression';
import { FINE } from '../lib/format';

const base = contratRobert as unknown as ContratTribunal;
const adapter = (contrat: ContratTribunal) =>
  adapterContrat(contrat, { nomProfil: 'Robert', titreDecision: '30 % en TSLA', audience: '1' });

describe('répliques', () => {
  const replique = { etiquette: 'fait' as const, texte: 'Votre Pacte fixe une limite.', pieces: [base.pieces[0].id],
    repond_a: { cote: 'plaidoirie' as const, numero: 1 } };
  const contrat: ContratTribunal = { ...base, requisitoire: [...base.requisitoire, replique] };

  it('une réplique garde l’argument adverse visé : camp, numéro et première phrase', () => {
    const argument = adapter(contrat).arguments.find((a) => a.texte === replique.texte)!;
    expect(argument.repondA).toEqual({ camp: 'Avocat', numero: 1, accroche: expect.any(String) });
    expect(base.plaidoirie[0].texte.startsWith(argument.repondA!.accroche.replace(/\.$/, ''))).toBe(true);
  });

  it('un argument ordinaire n’a pas de cible, et un procès enregistré avant #189 non plus', () => {
    expect(adapter(base).arguments.every((a) => a.repondA === undefined)).toBe(true);
  });

  it('l’étape de réplique appartient à sa phase', () => {
    expect(phaseDeLEtape({ etape: 'avocat', outil: 'bedrock_replique' })).toBe('replique');
    expect(phaseDeLEtape({ etape: 'avocat', outil: 'bedrock_correction' })).toBe('greffier');
  });
});

describe('instruction du dossier', () => {
  it('sépare les calculs choisis par l’orchestrateur de ceux ajoutés d’office par Python', () => {
    const choix = choixInstruction(adapter(base).trace);
    const origines = new Set(choix.map((c) => c.origine));
    expect(origines.has('orchestrateur')).toBe(true);
    expect(choix.filter((c) => c.origine === 'orchestrateur').every((c) => c.raison && c.piece)).toBe(true);
    expect(choix.filter((c) => c.origine === 'office').every((c) => /d.office/i.test(c.raison ?? ''))).toBe(true);
  });

  it('un appel refusé n’a pas de pièce', () => {
    const contrat: ContratTribunal = { ...base, trace: [...base.trace, { etape: 'orchestrateur', outil: 'mesurer_liquidite',
      raison: 'Voir si les lignes se revendent vite', entree: {}, sortie: 'Erreur : titre hors univers' }] };
    expect(choixInstruction(adapter(contrat).trace).at(-1)).toMatchObject({ origine: 'refuse', piece: undefined });
  });
});

describe('mesure Bedrock', () => {
  const bedrock: BedrockContrat = {
    modele: 'global.anthropic.claude-sonnet-5-5', appels: 7, jetons_entree: 51234, jetons_sortie: 7012,
    duree_bedrock_s: 52.4, cout_estime_usd: 0.1726, duree_proces_s: 41.2,
    par_agent: [{ agent: 'agent_profil', appels: 1, jetons_entree: 3000, jetons_sortie: 300 },
      { agent: 'orchestrateur', appels: 2, jetons_entree: 20000, jetons_sortie: 1000 }],
  };

  it('résume les appels par agent, les jetons, le coût estimé et la durée', () => {
    const [appels, jetons, duree] = resumeBedrock(bedrock);
    expect(appels).toBe('7 appels à Amazon Bedrock (Agent Profil 1, Orchestrateur 2)');
    expect(jetons).toBe(`51${FINE}234 jetons lus, 7${FINE}012 écrits · environ 0,17 $ US au tarif public`);
    expect(duree).toContain('Procès complet en 41 s');
    expect(resumeBedrock(bedrock)).toHaveLength(3); // sans Guardrail
  });

  it('ajoute le Guardrail quand il est configuré', () => {
    expect(resumeBedrock({ ...bedrock, garde_fou: { verifications: 9, interventions: 0 } }).at(-1))
      .toBe('Guardrail Bedrock : 9 textes contrôlés, 0 intervention');
  });

  it('chaque étape horodatée dit son moment depuis le début du procès', () => {
    const trace = base.trace.map((e, i) => ({ ...e, horodatage: new Date(Date.UTC(2026, 10, 15, 22, 0, i * 2)).toISOString() }));
    const etapes = adapter({ ...base, trace }).trace;
    expect(etapes[0].secondes).toBe(0);
    expect(etapes[3].secondes).toBe(6);
    expect(moment(12.4)).toBe('+12,4 s');
    expect(adapter(base).trace[0].secondes).toBeUndefined();
  });
});

describe('procès rejoués en démonstration (#189)', () => {
  it('avec le Pacte vécu aussi, le procès le plus récent est rejoué : répliques et mesure Bedrock', async () => {
    const calibrage = reponsesDuContrat(robertVecu as unknown as ContratTribunal)!;
    const resultat = await jugerDecision('robert', { type: 'position', ticker: 'TSLA', taille: 30 }, { calibrage });
    expect(resultat.procesId).toBe('2026-11-16-2e2faa67372b');
    expect(resultat.arguments.filter((a) => a.repondA)).toHaveLength(2);
    expect(resultat.contrat.bedrock?.garde_fou?.interventions).toBe(0);
  });
});
