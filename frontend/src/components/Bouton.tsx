/**
 * Bouton (annexe A.4) : primaire (encre, flèche →), secondaire (bordure 1,5 encre),
 * tertiaire (lien bleu). Un seul primaire par écran. Rendu en lien quand `vers` est donné.
 */
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Icone } from './Icone';
import styles from './Bouton.module.css';

type Variante = 'primaire' | 'secondaire' | 'tertiaire' | 'inverse';

interface ProprietesBouton extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  variante?: Variante;
  compact?: boolean;
  fleche?: boolean;
  vers?: string;
  icone?: ReactNode;
  children: ReactNode;
}

export function Bouton({ variante = 'secondaire', compact = false, fleche, vers, icone, children, className, ...reste }: ProprietesBouton) {
  const avecFleche = fleche ?? variante === 'primaire';
  const classes = [styles.bouton, styles[variante], compact ? styles.compact : styles.grand, className].filter(Boolean).join(' ');
  const contenu = (
    <>
      {icone}
      <span>{children}</span>
      {avecFleche && <Icone nom="fleche-droite" taille={16} epaisseur={2} />}
    </>
  );
  if (vers) {
    return (
      <Link to={vers} className={classes}>
        {contenu}
      </Link>
    );
  }
  return (
    <button type="button" className={classes} {...reste}>
      {contenu}
    </button>
  );
}
