/** Échelles et graduations des graphiques (aucune donnée inventée : elles ne font que placer les points). */
import { useLayoutEffect, useRef, useState } from 'react';

export function jour(iso: string): number {
  return Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) / 86_400_000;
}

export function echelleLineaire(domaine: [number, number], plage: [number, number]) {
  const [d0, d1] = domaine;
  const [p0, p1] = plage;
  const pente = d1 === d0 ? 0 : (p1 - p0) / (d1 - d0);
  return (v: number) => p0 + (v - d0) * pente;
}

/** Pas « rond » (1, 2, 2,5 ou 5 × 10ⁿ) pour environ `cible` intervalles. */
export function pasRond(etendue: number, cible = 4): number {
  const brut = etendue / cible;
  const puissance = 10 ** Math.floor(Math.log10(brut));
  const normalise = brut / puissance;
  const facteur = normalise <= 1 ? 1 : normalise <= 2 ? 2 : normalise <= 2.5 ? 2.5 : normalise <= 5 ? 5 : 10;
  return facteur * puissance;
}

/** Graduations multiples de `pas` comprises entre `min` et `max`. */
export function graduations(min: number, max: number, pas: number): number[] {
  const debut = Math.ceil(min / pas - 1e-9) * pas;
  const valeurs: number[] = [];
  for (let v = debut; v <= max + 1e-9; v += pas) valeurs.push(Number(v.toFixed(10)));
  return valeurs;
}

/** Premières séances de chaque année de la série, pour l'axe des abscisses. */
export function debutsAnnees(dates: string[]): { annee: string; date: string }[] {
  const vues = new Set<string>();
  const resultat: { annee: string; date: string }[] = [];
  for (const d of dates) {
    const annee = d.slice(0, 4);
    if (!vues.has(annee)) {
      vues.add(annee);
      if (d.slice(5, 7) === '01') resultat.push({ annee, date: d });
    }
  }
  return resultat;
}

export function chemin(points: [number, number][]): string {
  return points.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join('');
}

/** Largeur réelle du conteneur, pour dessiner le SVG au pixel près sans déformer le texte. */
export function useLargeur<T extends HTMLElement>(initiale: number) {
  const ref = useRef<T>(null);
  const [largeur, setLargeur] = useState(initiale);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return undefined;
    const mesurer = () => setLargeur(Math.max(280, Math.round(element.getBoundingClientRect().width)));
    mesurer();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const observateur = new ResizeObserver(mesurer);
    observateur.observe(element);
    return () => observateur.disconnect();
  }, []);
  return [ref, largeur] as const;
}
