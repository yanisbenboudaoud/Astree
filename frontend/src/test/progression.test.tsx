/**
 * Progression du procès en direct (#90) : relecture de /progression (faux serveur), écran de
 * chargement, et relecture d'un procès enregistré en mode démonstration.
 */
import { render, screen, within } from '@testing-library/react';
import contratRobert from '../data/proces/2026-11-15-fe7e9832703a.json';
import contratAmira from '../data/proces/2026-11-15-b6795c03a385.json';
import type { ContratTribunal, EtapeTraceContrat, ProgressionContrat } from '../api/contrat';
import type { ProgressionTribunal } from '../api/types';
import { etapeTrace } from '../api/adaptateur';
import { AVIS_OCCUPE, suivreProces } from '../api/tribunal';
import { ChargementTribunal } from '../components/ChargementTribunal';
import { PHASES, etatsDesPhases, phaseDeLEtape, phaseEnRelecture, renvoisDuGreffier } from '../domaine/progression';

const PROFIL: EtapeTraceContrat = { etape: 'agent_profil', outil: 'charger_pacte', entree: 'robert', sortie: 'P1' };
const SIMULATION: EtapeTraceContrat = {
  etape: 'orchestrateur', outil: 'simuler_portefeuille', raison: "Pièce obligatoire ajoutée d'office",
  entree: { ticker: 'TSLA', taille: 0.3, financement: 'proportionnel', periode: 'complete' }, sortie: 'P2',
};
const INDICATEURS: EtapeTraceContrat = {
  etape: 'orchestrateur', outil: 'indicateurs_actif', raison: 'Mesurer le risque propre du titre', entree: { ticker: 'TSLA' }, sortie: 'P3',
};
const CORRECTION: EtapeTraceContrat = { etape: 'procureur', outil: 'bedrock_correction', entree: {}, sortie: {} };

function document(phase: string | null, etapes: EtapeTraceContrat[], activite?: string): ProgressionContrat {
  return { id: '2026-11-15-0123456789ab', statut: 'en_cours', phase, etapes, activite };
}

/** Faux /progression : une réponse par relecture, dans l'ordre. */
function fauxServeur(reponses: (ProgressionContrat | number)[]) {
  const corps: string[] = [];
  const requete = (async (_url: string, init?: RequestInit) => {
    corps.push(String(init?.body));
    const suivante = reponses.shift();
    if (typeof suivante === 'number') return new Response('{}', { status: suivante });
    return new Response(JSON.stringify(suivante), { status: 200 });
  }) as typeof fetch;
  return { requete, corps };
}

const sansAttente = { attendre: async () => undefined, intervalleMs: 1500 };

describe('relecture de /progression', () => {
  it('la phase en cours change à chaque relecture et les outils arrivent un par un', async () => {
    const contrat = { persona: 'robert' } as unknown as ContratTribunal;
    const { requete, corps } = fauxServeur([
      document('agent_profil', [], 'Lecture de la demande'),
      document('orchestrateur', [PROFIL]),
      document('orchestrateur', [PROFIL, SIMULATION]),
      document('orchestrateur', [PROFIL, SIMULATION, INDICATEURS]),
      document('debat', [PROFIL, SIMULATION, INDICATEURS]),
      { id: '2026-11-15-0123456789ab', statut: 'termine', contrat },
    ]);
    const vues: ProgressionTribunal[] = [];

    const resultat = await suivreProces('https://lambda', '2026-11-15-0123456789ab', { ...sansAttente, requete, onProgression: (p) => vues.push(p) });

    expect(resultat).toEqual(contrat);
    expect(vues.map((v) => v.phase)).toEqual(['agent_profil', 'orchestrateur', 'orchestrateur', 'orchestrateur', 'debat']);
    const outils = vues.map((v) => v.etapes.filter((e) => e.phase === 'orchestrateur').map((e) => e.sortie));
    expect(outils).toEqual([[], [], ['P2'], ['P2', 'P3'], ['P2', 'P3']]);
    expect(vues[0].activite).toBe('Lecture de la demande');
    expect(JSON.parse(corps[0])).toEqual({ id: '2026-11-15-0123456789ab' });
  });

  it('une erreur du procès arrête la relecture avec son motif', async () => {
    const { requete } = fauxServeur([{ id: 'x', statut: 'erreur', erreur: 'Bedrock indisponible' }]);
    await expect(suivreProces('https://lambda', 'x', { ...sansAttente, requete })).rejects.toThrow('Bedrock indisponible');
  });

  it('Tribunal occupé (429) : un avis, puis la relecture continue', async () => {
    const contrat = { persona: 'robert' } as unknown as ContratTribunal;
    const { requete } = fauxServeur([document('orchestrateur', [SIMULATION]), 429, { id: 'x', statut: 'termine', contrat }]);
    const vues: ProgressionTribunal[] = [];
    await expect(suivreProces('https://lambda', 'x', { ...sansAttente, requete, onProgression: (p) => vues.push(p) })).resolves.toEqual(contrat);
    expect(vues[1].avis).toBe(AVIS_OCCUPE);
    expect(vues[1].etapes).toHaveLength(1); // la dernière progression connue reste affichée
  });

  it('procès inconnu (404) : erreur lisible', async () => {
    const requete = (async () => new Response(JSON.stringify({ erreur: 'Aucun procès en cours avec l’identifiant x' }), { status: 404 })) as typeof fetch;
    await expect(suivreProces('https://lambda', 'x', { ...sansAttente, requete })).rejects.toThrow('Aucun procès en cours');
  });

  it('arrêtée après le délai maximal, sans relire indéfiniment', async () => {
    let horloge = 0;
    const requete = (async () => new Response(JSON.stringify(document('debat', [])), { status: 200 })) as typeof fetch;
    const appels = vi.fn(async () => { horloge += 1500; });
    await expect(suivreProces('https://lambda', 'x', { requete, attendre: appels, maintenant: () => horloge, delaiMaxMs: 120_000 }))
      .rejects.toThrow('120 s');
    expect(appels).toHaveBeenCalledTimes(80); // une relecture toutes les 1,5 s pendant 120 s
  });

  it('quitter l’écran (AbortSignal) arrête la relecture', async () => {
    const controleur = new AbortController();
    const requete = (async () => {
      controleur.abort();
      throw new DOMException('Interrompu', 'AbortError');
    }) as typeof fetch;
    await expect(suivreProces('https://lambda', 'x', { ...sansAttente, requete, signal: controleur.signal })).rejects.toThrow('Interrompu');
  });
});

describe('écran « Le Tribunal instruit le dossier »', () => {
  const etapes = [PROFIL, SIMULATION, INDICATEURS].map(etapeTrace);

  it('phase en cours animée, phases finies cochées, outils de l’orchestrateur listés', () => {
    render(<ChargementTribunal mode="direct" phase="orchestrateur" etapes={etapes} termine={false} debut={Date.now()}
      activite="L'orchestrateur choisit les preuves à rassembler (Bedrock)" />);
    const phases = screen.getAllByRole('listitem').filter((li) => li.hasAttribute('data-etat'));
    expect(phases.map((li) => li.getAttribute('data-etat'))).toEqual(['faite', 'en_cours', 'a_venir', 'a_venir']);
    expect(phases[1]).toHaveAttribute('aria-current', 'step');
    const orchestrateur = within(phases[1]);
    expect(orchestrateur.getByText(/^Simuler votre portefeuille avec 30\s%\sen TSLA$/)).toBeInTheDocument();
    expect(orchestrateur.getByText(/Pièce obligatoire ajoutée d'office/)).toBeInTheDocument();
    expect(orchestrateur.getByText('Mesurer le risque de TSLA seul')).toBeInTheDocument();
    expect(orchestrateur.getByText('P3')).toBeInTheDocument();
    // L'appel technique reste lisible dans la trace repliée.
    expect(screen.getByText(/Orchestrateur · indicateurs_actif\(ticker: TSLA\) → P3/)).toBeInTheDocument();
    expect(orchestrateur.getByText("L'orchestrateur choisit les preuves à rassembler (Bedrock)…")).toBeInTheDocument();
    expect(screen.getByText('Phase en cours : Orchestrateur')).toBeInTheDocument(); // annoncé aux lecteurs d'écran
  });

  it('renvois du Greffier et avis sur le suivi', () => {
    render(<ChargementTribunal mode="direct" phase="greffier" etapes={[...etapes, etapeTrace(CORRECTION)]} termine={false}
      debut={Date.now()} avis={AVIS_OCCUPE} />);
    expect(screen.getByText('1 argument renvoyé au Procureur')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Le Tribunal est occupé');
  });

  it('relecture d’un procès enregistré : annoncée, avec son rythme', () => {
    render(<ChargementTribunal mode="relecture" phase="agent_profil" etapes={[]} termine={false} debut={Date.now()} dureeEtapeMs={500} />);
    expect(screen.getByText(/Relecture d'un procès enregistré.*une étape toutes les 0,5 s/)).toBeInTheDocument();
  });
});

describe('relecture d’un procès enregistré (mode démonstration)', () => {
  it.each([['robert', contratRobert], ['amira', contratAmira]])('la trace de %s se rejoue phase par phase, dans l’ordre', (_nom, contrat) => {
    const trace = (contrat as unknown as ContratTribunal).trace.map(etapeTrace);
    const phases = Array.from({ length: trace.length + 1 }, (_, n) => phaseEnRelecture(trace, n));
    expect(phases[0]).toBe('agent_profil');
    expect(phases[trace.length]).toBeNull(); // toute la trace affichée : instruction terminée
    const vues = phases.filter((p): p is NonNullable<typeof p> => p !== null);
    const rangs = vues.map((p) => PHASES.findIndex((ph) => ph.id === p));
    expect(rangs).toEqual([...rangs].sort((a, b) => a - b)); // jamais de retour en arrière
    expect(new Set(vues)).toEqual(new Set(['agent_profil', 'orchestrateur', 'debat', 'greffier']));
  });

  it('chaque étape d’un procès enregistré a sa phase', () => {
    const trace = (contratRobert as unknown as ContratTribunal).trace;
    expect(trace.map(phaseDeLEtape).every((p) => PHASES.some((ph) => ph.id === p))).toBe(true);
  });
});

describe('états des phases', () => {
  it('avant, pendant et après', () => {
    expect(Object.values(etatsDesPhases(null, false))).toEqual(['a_venir', 'a_venir', 'a_venir', 'a_venir']);
    expect(Object.values(etatsDesPhases('debat', false))).toEqual(['faite', 'faite', 'en_cours', 'a_venir']);
    expect(Object.values(etatsDesPhases(null, true))).toEqual(['faite', 'faite', 'faite', 'faite']);
  });

  it('renvois comptés par agent', () => {
    const corrections = [CORRECTION, CORRECTION, { ...CORRECTION, etape: 'avocat' }].map(etapeTrace);
    expect(renvoisDuGreffier(corrections)).toEqual(['2 arguments renvoyés au Procureur', "1 argument renvoyé à l'Avocat"]);
  });
});
