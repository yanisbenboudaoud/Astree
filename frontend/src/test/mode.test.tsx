/**
 * Mode choisi à l'utilisation (#137) : mode de la construction par défaut, `?mode=` dans l'adresse,
 * mémorisation dans localStorage (le site marche sans), aucun mode direct sans adresse de Lambda,
 * et `?mode=demo` sur un site construit en direct : aucun appel à la Lambda pendant le rejeu.
 */
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { choisirMode, modeDemande } from '../api/config';

const URL_LAMBDA = 'https://exemple.lambda-url.us-east-1.on.aws';

interface Page {
  recherche?: string;
  construction?: 'direct' | 'demo';
  urlApi?: string;
}

/** Recharge les modules comme au chargement d'une page : adresse, variables de construction, stockage. */
async function chargerPage({ recherche = '', construction = 'direct', urlApi = URL_LAMBDA }: Page = {}) {
  vi.resetModules();
  vi.stubEnv('VITE_USE_MOCKS', construction === 'direct' ? 'false' : 'true');
  vi.stubEnv('VITE_API_URL', urlApi);
  window.history.replaceState(null, '', `/${recherche}`);
  return import('../api/config');
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
  sessionStorage.clear();
  window.history.replaceState(null, '', '/');
});

describe('choix du mode (logique pure)', () => {
  const base = { recherche: '', memorise: null, construction: 'direct' as const, directDisponible: true };

  it('par défaut : le mode de la construction', () => {
    expect(choisirMode(base)).toBe('direct');
    expect(choisirMode({ ...base, construction: 'demo' })).toBe('demo');
  });

  it('?mode= dans l’adresse l’emporte sur le mode mémorisé et sur la construction', () => {
    expect(choisirMode({ ...base, recherche: '?mode=demo', memorise: 'direct' })).toBe('demo');
    expect(choisirMode({ ...base, recherche: '?mode=direct', memorise: 'demo', construction: 'demo' })).toBe('direct');
  });

  it('le mode mémorisé l’emporte sur la construction ; une valeur inconnue est ignorée', () => {
    expect(choisirMode({ ...base, memorise: 'demo' })).toBe('demo');
    expect(choisirMode({ ...base, recherche: '?mode=bidon', memorise: 'autre' })).toBe('direct');
  });

  it('sans adresse de Lambda : toujours la démonstration', () => {
    expect(choisirMode({ recherche: '?mode=direct', memorise: 'direct', construction: 'direct', directDisponible: false })).toBe('demo');
  });

  it('lit ?mode= parmi les autres paramètres', () => {
    expect(modeDemande('?piece=P1&mode=demo')).toBe('demo');
    expect(modeDemande('')).toBeNull();
    expect(modeDemande('?mode=DIRECT')).toBeNull();
  });
});

describe('au chargement de la page', () => {
  it('site construit en direct, sans paramètre : mode direct, rien n’est mémorisé', async () => {
    const config = await chargerPage();
    expect(config.MODE).toBe('direct');
    expect(config.MODE_DIRECT).toBe(true);
    expect(config.DIRECT_DISPONIBLE).toBe(true);
    expect(localStorage.getItem(config.CLE_MODE)).toBeNull();
  });

  it('?mode=demo : procès enregistrés, mémorisés pour les visites suivantes', async () => {
    const config = await chargerPage({ recherche: '?mode=demo' });
    expect(config.MODE).toBe('demo');
    expect(localStorage.getItem(config.CLE_MODE)).toBe('demo');

    const suivante = await chargerPage({ recherche: '' });
    expect(suivante.MODE).toBe('demo');
  });

  it('?mode=direct sur un site construit en démonstration (avec l’adresse de la Lambda)', async () => {
    const config = await chargerPage({ recherche: '?mode=direct', construction: 'demo' });
    expect(config.MODE).toBe('direct');
  });

  it('sans localStorage (navigation privée, bloqué) : le site marche, ?mode= vaut pour la page', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('bloqué'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('bloqué'); });
    expect((await chargerPage({ recherche: '?mode=demo' })).MODE).toBe('demo');
    expect((await chargerPage({ recherche: '' })).MODE).toBe('direct'); // rien de mémorisé : la construction
  });

  it('sans VITE_API_URL : démonstration, même avec ?mode=direct, et rien n’est mémorisé', async () => {
    const config = await chargerPage({ recherche: '?mode=direct', urlApi: '' });
    expect(config.MODE).toBe('demo');
    expect(config.DIRECT_DISPONIBLE).toBe(false);
    expect(localStorage.getItem(config.CLE_MODE)).toBeNull();
  });

  it('état de session propre à chaque mode ; la démonstration garde la clé d’origine', async () => {
    expect((await chargerPage()).cleSession('astree.etat.v1')).toBe('astree.etat.v1.direct');
    expect((await chargerPage({ recherche: '?mode=demo' })).cleSession('astree.etat.v1')).toBe('astree.etat.v1');
  });

  it('changer de mode : mémorisé, puis retour à l’accueil avec ?mode=', async () => {
    const config = await chargerPage();
    const aller = vi.fn();
    config.changerMode('demo', aller);
    expect(localStorage.getItem(config.CLE_MODE)).toBe('demo');
    expect(aller).toHaveBeenCalledWith('/?mode=demo');
  });
});

describe('?mode=demo sur le site construit en direct', () => {
  it('rejoue le procès enregistré et garde le verdict sans aucun appel à la Lambda', async () => {
    await chargerPage({ recherche: '?mode=demo' });
    const requete = vi.fn(() => Promise.reject(new Error('appel réseau inattendu')));
    vi.stubGlobal('fetch', requete);
    const { jugerDecision, archiverVerdict, questionLibreDisponible } = await import('../api/tribunal');

    const resultat = await jugerDecision('robert', { type: 'position', ticker: 'TSLA', taille: 30 });
    expect(resultat.procesId).toBeTruthy();
    expect(resultat.arguments.length).toBeGreaterThan(0);
    await archiverVerdict(resultat.procesId, 'maintenu');
    expect(questionLibreDisponible(resultat.procesId)).toBe(false); // question libre : Bedrock, direct seulement
    expect(requete).not.toHaveBeenCalled();
  });

  it('en direct (défaut du site), le même procès part à la Lambda', async () => {
    await chargerPage();
    const requete = vi.fn(() => Promise.reject(new Error('Lambda injoignable dans le test')));
    vi.stubGlobal('fetch', requete);
    const { jugerDecision } = await import('../api/tribunal');

    await expect(jugerDecision('robert', { type: 'position', ticker: 'TSLA', taille: 30 })).rejects.toThrow('injoignable');
    expect(requete).toHaveBeenCalledWith(`${URL_LAMBDA}/tribunal`, expect.objectContaining({ method: 'POST' }));
  });
});

describe('interrupteur du bandeau', () => {
  async function afficherGabarit() {
    const { Gabarit } = await import('../components/Gabarit');
    render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><Gabarit><p>Contenu</p></Gabarit></MemoryRouter>);
  }

  it('absent sans VITE_API_URL : le mode direct n’est pas proposé', async () => {
    await chargerPage({ urlApi: '' });
    await afficherGabarit();
    expect(screen.getByText(/aucune transaction réelle/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Mode :/ })).toBeNull();
  });

  it('présent avec l’adresse de la Lambda : les deux modes, une phrase chacun, retour à l’accueil', async () => {
    await chargerPage();
    await afficherGabarit();
    const bouton = screen.getByRole('button', { name: 'Mode : En direct (Bedrock sur AWS)' });
    expect(bouton).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(bouton);

    const panneau = screen.getByRole('dialog', { name: 'Mode de l’interface' });
    expect(within(panneau).getByText(/mode actuel/)).toBeInTheDocument();
    expect(within(panneau).getByText(/sur AWS Lambda et Amazon Bedrock/)).toBeInTheDocument();
    expect(within(panneau).getByText(/sans nouvel appel à Bedrock/)).toBeInTheDocument();
    expect(within(panneau).getByText('Changer de mode ramène à l’accueil.')).toBeInTheDocument();
    expect(within(panneau).queryByRole('button', { name: 'Passer en direct' })).toBeNull();

    vi.spyOn(console, 'error').mockImplementation(() => {}); // jsdom ne sait pas naviguer
    fireEvent.click(within(panneau).getByRole('button', { name: 'Passer aux procès enregistrés' }));
    expect(localStorage.getItem('astree.mode')).toBe('demo');
  });

  it('en procès enregistrés, l’interrupteur propose de passer en direct', async () => {
    await chargerPage({ recherche: '?mode=demo' });
    await afficherGabarit();
    fireEvent.click(screen.getByRole('button', { name: 'Mode : Procès enregistrés' }));
    expect(screen.getByRole('button', { name: 'Passer en direct' })).toBeInTheDocument();
  });
});
