import { fireEvent, render, screen } from '@testing-library/react';
import { GraphiqueValeur, indiceLePlusProche } from '../components/graphiques/GraphiqueValeur';
import { dollars } from '../lib/format';

const serie: [string, number][] = [
  ['2021-11-12', 416966],
  ['2021-11-19', 416375],
  ['2021-11-26', 414050],
  ['2022-01-07', 402000],
  ['2026-11-12', 650000],
];
const pointBas = { date: '2022-01-07', valeur: 402000, recul: -0.0359 };

describe('indiceLePlusProche', () => {
  it('rend le point le plus proche, bornes comprises', () => {
    const abscisses = [0, 10, 20, 40];
    expect(indiceLePlusProche(abscisses, -5)).toBe(0);
    expect(indiceLePlusProche(abscisses, 14)).toBe(1);
    expect(indiceLePlusProche(abscisses, 16)).toBe(2);
    expect(indiceLePlusProche(abscisses, 99)).toBe(3);
  });
});

describe('GraphiqueValeur', () => {
  it('n’affiche aucune lecture tant qu’on ne survole pas', () => {
    render(<GraphiqueValeur serie={serie} pointBas={pointBas} />);
    expect(screen.queryByTestId('lecture-valeur')).toBeNull();
  });

  it('se parcourt au clavier et lit les valeurs de la série telles quelles', () => {
    render(<GraphiqueValeur serie={serie} pointBas={pointBas} />);
    const graphique = screen.getByRole('img');
    fireEvent.focus(graphique);
    const lecture = () => screen.getByTestId('lecture-valeur').textContent;
    expect(lecture()).toContain(dollars(650_000));
    fireEvent.keyDown(graphique, { key: 'Home' });
    expect(lecture()).toContain(dollars(416_966));
    fireEvent.keyDown(graphique, { key: 'ArrowRight' });
    expect(lecture()).toContain(dollars(416_375));
    fireEvent.keyDown(graphique, { key: 'ArrowLeft' });
    fireEvent.keyDown(graphique, { key: 'ArrowLeft' });
    expect(lecture()).toContain(dollars(416_966));
    fireEvent.keyDown(graphique, { key: 'PageDown' });
    expect(lecture()).toContain(dollars(650_000));
    fireEvent.keyDown(graphique, { key: 'Escape' });
    expect(screen.queryByTestId('lecture-valeur')).toBeNull();
  });

  it('annonce la lecture aux lecteurs d’écran', () => {
    const { container } = render(<GraphiqueValeur serie={serie} pointBas={pointBas} />);
    fireEvent.focus(screen.getByRole('img'));
    fireEvent.keyDown(screen.getByRole('img'), { key: 'Home' });
    expect(container.querySelector('[aria-live="polite"]')?.textContent).toBe(`12 nov. 2021 : ${dollars(416966)}`);
  });
});
