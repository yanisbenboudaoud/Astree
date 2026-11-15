import { fireEvent, render, screen } from '@testing-library/react';
import { GraphiqueRecul } from '../components/graphiques/GraphiqueRecul';
import { pourcent } from '../lib/format';

const actuel: [string, number][] = [
  ['2021-11-12', 0],
  ['2022-06-17', -0.145],
  ['2022-12-30', -0.151],
  ['2026-11-12', -0.01],
];
const decision: [string, number][] = [
  ['2021-11-12', 0],
  ['2022-06-17', -0.176],
  ['2022-12-30', -0.2031],
  ['2026-11-12', -0.02],
];
const base = {
  actuel,
  decision,
  limite: -0.2,
  creux: { date: '2022-12-30', valeur: -0.2031 },
  creuxActuel: { date: '2022-12-30', valeur: -0.151 },
  libelleDecision: 'Avec 12 % de TSLA',
};

describe('GraphiqueRecul', () => {
  it('dit en une phrase que la limite est franchie, au singulier pour une séance', () => {
    render(<GraphiqueRecul {...base} seances={{ nombre: 1, du: '2022-12-30', au: '2022-12-30' }} />);
    expect(screen.getByText(/pendant 1 séance, en déc\. 2022/)).toBeInTheDocument();
  });

  it('dit quand la limite n’est jamais franchie', () => {
    render(<GraphiqueRecul {...base} seances={{ nombre: 0, du: null, au: null }} />);
    expect(screen.getByText(/ne serait jamais passé sous votre limite/)).toBeInTheDocument();
  });

  it('compare les deux courbes à la même date, au clavier', () => {
    render(<GraphiqueRecul {...base} seances={{ nombre: 1, du: '2022-12-30', au: '2022-12-30' }} />);
    const graphique = screen.getByRole('img');
    fireEvent.keyDown(graphique, { key: 'ArrowLeft' });
    const lecture = screen.getByTestId('lecture-recul').textContent;
    expect(lecture).toContain(pourcent(-0.145));
    expect(lecture).toContain(pourcent(-0.176));
    fireEvent.keyDown(graphique, { key: 'Escape' });
    expect(screen.queryByTestId('lecture-recul')).toBeNull();
  });
});
