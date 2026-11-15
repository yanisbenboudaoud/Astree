/**
 * « Construire mon Pacte » (#86) : logique pure du questionnaire, et parcours de l'écran en
 * mode démonstration (le mode est forcé ici : .env.local peut mettre l'interface en direct).
 */
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api/config', async (original) => ({
  ...(await original<typeof import('../api/config')>()),
  MODE_DIRECT: false,
  URL_API: '',
}));

const { QUESTIONS, PacteNonDisponible, apercuPacte, estSaisieDemo, saisieDemo, signerPacte } = await import('../api/questionnaire');
const { profil, donneesCalibrage } = await import('../api/donnees');
const {
  basculerChoixMultiple, blocage, erreurPortefeuille, libelleReponse, raisonsRegle, reponsesNettoyees, sections, valeurDepuisPoints,
} = await import('../domaine/questionnaire');
const { ConstruireMonPacte } = await import('../ecrans/ConstruireMonPacte');

const question = (id: string) => QUESTIONS.find((q) => q.id === id)!;

window.scrollTo = vi.fn() as unknown as typeof window.scrollTo; // jsdom ne fait pas défiler

describe('questions venues du pipeline', () => {
  it('16 questions en 5 sections, dans l’ordre', () => {
    expect(QUESTIONS).toHaveLength(16); // dont « hors du Canada », facultative (#112)
    expect(sections(QUESTIONS).map((s) => s.titre.split(' : ')[0])).toEqual([
      'Objectif et horizon', 'Capacité', 'Tolérance', 'Connaissances et expérience', 'Préférences et limites',
    ]);
  });

  it('la question des portefeuilles (cartes) n’est plus posée', () => {
    expect(QUESTIONS.map((q) => q.id)).not.toContain('fourchettes');
  });
});

describe('logique du questionnaire', () => {
  it('une question obligatoire sans réponse bloque ; une facultative se passe', () => {
    expect(blocage(question('horizon'), undefined)).toMatch(/obligatoire/);
    expect(blocage(question('horizon'), '5_10')).toBeNull();
    expect(blocage(question('coussin'), undefined)).toBeNull();
  });

  it('texte trop long refusé', () => {
    expect(blocage(question('regle_perso'), 'x'.repeat(121))).toMatch(/120 caractères/);
  });

  it('« aucune » exclut les autres choix, et inversement', () => {
    expect(basculerChoixMultiple(['energies_fossiles'], 'aucune')).toEqual(['aucune']);
    expect(basculerChoixMultiple(['aucune'], 'energies_fossiles')).toEqual(['energies_fossiles']);
    expect(basculerChoixMultiple(['fonds'], 'fonds')).toEqual([]);
  });

  it('les questions passées ne sont pas envoyées', () => {
    expect(reponsesNettoyees({ horizon: '5_10', regle_perso: '  ', exclusions: [], objectif: 'projet' }))
      .toEqual({ horizon: '5_10', objectif: 'projet' });
  });

  it('portefeuille : un titre, sans doublon, total de 100 %', () => {
    expect(erreurPortefeuille([{ ticker: '', poids: 1 }], 1000)).toMatch(/au moins un titre/);
    expect(erreurPortefeuille([{ ticker: 'SPY', poids: 0.5 }, { ticker: 'SPY', poids: 0.5 }], 1000)).toMatch(/qu’une fois/);
    expect(erreurPortefeuille([{ ticker: 'SPY', poids: 0.6 }, { ticker: 'XBB.TO', poids: 0.3 }], 1000)).toMatch(/100 %/);
    expect(erreurPortefeuille([{ ticker: 'SPY', poids: 1 }], 0)).toMatch(/capital/);
    expect(erreurPortefeuille([{ ticker: 'SPY', poids: 1 / 3 }, { ticker: 'XBB.TO', poids: 1 / 3 }, { ticker: 'XIU.TO', poids: 1 / 3 }], 1000)).toBeNull();
  });

  it('seuil saisi en points : pire baisse négative, plafond positif', () => {
    const pireBaisse = { id: 'pire_baisse_max', type: 'pire_baisse_max' as const, libelle: '', justification: '', seuil: -0.2 };
    const plafond = { id: 'plafond_tech', type: 'plafond' as const, libelle: '', justification: '', max: 0.5 };
    expect(valeurDepuisPoints(pireBaisse, 15)).toBe(-0.15);
    expect(valeurDepuisPoints(pireBaisse, -12.5)).toBe(-0.125);
    expect(valeurDepuisPoints(plafond, 25)).toBe(0.25);
  });

  it('« Parce que vous avez répondu » relit le barème de Python', async () => {
    const { bareme } = await apercuPacte(saisieDemo());
    expect(raisonsRegle('plafond_crypto', bareme, QUESTIONS)).toEqual(['Cryptoactifs : Aucune']);
    expect(libelleReponse(question('exclusions'), ['energies_fossiles'])).toBe('Énergies fossiles');
  });
});

describe('mode démonstration', () => {
  beforeEach(() => sessionStorage.clear());

  it('seul l’exemple préenregistré devient un Pacte ; toute autre saisie est refusée', async () => {
    const demo = saisieDemo();
    expect(estSaisieDemo(demo)).toBe(true);
    await expect(apercuPacte({ ...demo, capital: demo.capital + 1 })).rejects.toBeInstanceOf(PacteNonDisponible);
    await expect(apercuPacte({ ...demo, modifications: { pire_baisse_max: -0.15 } })).rejects.toBeInstanceOf(PacteNonDisponible);
  });

  it('signer rend le profil disponible pour les autres écrans', async () => {
    const signe = await signerPacte(saisieDemo());
    expect(profil(signe.id)?.nom).toBe(saisieDemo().nom);
    expect(donneesCalibrage(signe.id)?.episodes.length).toBeGreaterThan(0);
  });
});

function afficher() {
  return render(
    <MemoryRouter initialEntries={['/construire']}>
      <Routes>
        <Route path="/construire" element={<ConstruireMonPacte />} />
        <Route path="/:profil/pacte-vecu" element={<p>Écran Revivez 4 jours</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('écran Construire mon Pacte', () => {
  beforeEach(() => sessionStorage.clear());

  it('progression, réponse obligatoire signalée, retour arrière', () => {
    afficher();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '1');
    expect(screen.getByText(/il ne constitue pas un conseil financier/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Suivante/ }));
    expect(screen.getByRole('alert')).toHaveTextContent('obligatoire');
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '1');

    fireEvent.click(screen.getByLabelText('5 à 10 ans'));
    fireEvent.click(screen.getByRole('button', { name: /Suivante/ }));
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '2');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(question('objectif').libelle);

    fireEvent.click(screen.getByRole('button', { name: /Passer cette question/ }));
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '3');

    fireEvent.click(screen.getByRole('button', { name: /Précédente/ }));
    fireEvent.click(screen.getByRole('button', { name: /Précédente/ }));
    expect(screen.getByLabelText('5 à 10 ans')).toBeChecked(); // la réponse est gardée
  });

  it('profil de test : aperçu des règles avec leurs réponses, puis signature', async () => {
    afficher();
    fireEvent.click(screen.getByRole('button', { name: /Remplir comme un profil de test/ }));
    const regles = await screen.findByRole('region', { name: 'Les règles de votre Pacte' });
    expect(within(regles).getByText('Crypto : exclue')).toBeInTheDocument();
    expect(within(regles).getByText(/Parce que vous avez répondu : Cryptoactifs : Aucune/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Signer mon Pacte/ }));
    expect(await screen.findByText('Écran Revivez 4 jours')).toBeInTheDocument();
  });
});
