import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { INDICATEURS, LIMITES, LIMITES_PAR_ECRAN } from '../domaine/limites';
import { InfoLimite, LimitesDonnees } from '../components/Limites';

describe('catalogue des limites', () => {
  it('chaque écran ne cite que des limites qui existent, sans doublon', () => {
    for (const limites of Object.values(LIMITES_PAR_ECRAN)) {
      expect(new Set(limites).size).toBe(limites.length);
      for (const cle of limites) expect(LIMITES[cle]).toBeDefined();
    }
  });

  it('la période d’analyse est explicitée (énoncé : période explicitée)', () => {
    expect(LIMITES.periode.texte).toMatch(/12 nov\. 2021 au 12 nov\. 2026/);
  });

  it('la volatilité est présentée comme un indicateur de risque parmi d’autres', () => {
    expect(INDICATEURS.volatilite.limite).toMatch(/parmi d’autres/);
    expect(LIMITES.risque.texte).toMatch(/horizon, la diversification et vos préférences/);
  });

  it('aucune phrase ne promet ni ne conseille', () => {
    const textes = [...Object.values(LIMITES).flatMap((l) => [l.titre, l.texte]),
      ...Object.values(INDICATEURS).flatMap((i) => [i.mesure, i.limite])].join(' ');
    expect(textes).not.toMatch(/garanti(?!t)|vous devriez|recommand|rapportera|va monter/i);
  });
});

describe('composants des limites', () => {
  it('ⓘ ouvre ce que mesure l’indicateur et sa limite, Échap le ferme', () => {
    render(<InfoLimite indicateur="pire_baisse" libelle="Chute maximale" />);
    const bouton = screen.getByRole('button', { name: /Chute maximale : ce que mesure ce chiffre/ });
    expect(bouton).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(bouton);
    expect(screen.getByRole('note')).toHaveTextContent(INDICATEURS.pire_baisse.limite);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('note')).toBeNull();
  });

  it('« Ce que ces chiffres ne disent pas » est replié, puis liste les limites de l’écran', () => {
    render(<LimitesDonnees ecran="decision" />);
    const bouton = screen.getByRole('button', { name: /Ce que ces chiffres ne disent pas/ });
    expect(screen.getByText(LIMITES.simulation.titre)).not.toBeVisible();
    fireEvent.click(bouton);
    for (const cle of LIMITES_PAR_ECRAN.decision) expect(screen.getByText(LIMITES[cle].titre)).toBeVisible();
  });
});
