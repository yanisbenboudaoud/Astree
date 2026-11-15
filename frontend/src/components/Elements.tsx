/** Petits éléments de la maquette : monogramme, jauge, message, lien de retour, titre de section. */
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { tickerCourt } from '../lib/format';
import { Icone } from './Icone';
import { Bouton } from './Bouton';
import styles from './Elements.module.css';

/** Carré de 36 px avec le ticker court. Pas de logos d'entreprises. */
export function Monogramme({ ticker, className }: { ticker: string; className?: string }) {
  return (
    <span className={`${styles.monogramme} ${className ?? ''}`} aria-hidden="true">
      {tickerCourt(ticker)}
    </span>
  );
}

/** Jauge : piste de 6 px, remplissage encre-700, repère de limite en encre (à 100 %). */
export function Jauge({ valeur, libelle, largeur }: { valeur: number; libelle: string; largeur?: number }) {
  const borne = Math.max(0, Math.min(1, valeur));
  return (
    <span
      className={styles.jauge}
      style={largeur ? { width: largeur } : undefined}
      role="meter"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(valeur * 100)}
      aria-label={libelle}
    >
      <span className={styles.piste} />
      <span className={styles.rempli} style={{ width: `${borne * 100}%` }} />
      <span className={styles.limite} />
    </span>
  );
}

interface ProprietesMessage {
  type: 'Violation' | 'À vérifier';
  titre: string;
  children: ReactNode;
  correction?: { libelle: string; onClick: () => void };
  aide?: string;
}

/** « Cette taille enfreint votre Pacte (§1) » → titre sans renvoi + « §1 », affiché dans l'étiquette. */
function separerParagraphe(titre: string): { titre: string; paragraphe?: string } {
  const trouve = titre.match(/^(.*?)\s*\((?:Pacte\s*)?(§\d+)\)$/);
  return trouve ? { titre: trouve[1], paragraphe: trouve[2] } : { titre };
}

/** Message : carte blanche, pastille d'icône teintée, étiquette de statut, pied séparé pour la correction. */
export function Message({ type, titre, children, correction, aide }: ProprietesMessage) {
  const violation = type === 'Violation';
  const { titre: titreCourt, paragraphe } = separerParagraphe(titre);
  return (
    <section className={`${styles.message} ${violation ? styles.messageViolation : styles.messageVerifier}`} aria-label={`${type} : ${titre}`}>
      <div className={styles.enteteMessage}>
        <span className={styles.iconeMessage}>
          <Icone nom={violation ? 'interdit' : 'alerte'} taille={18} />
        </span>
        <div className={styles.texteMessage}>
          <span className={styles.statutMessage}>
            {violation ? 'Hors Pacte' : 'À vérifier'}
            {paragraphe && <span className={styles.paragrapheMessage}>Pacte {paragraphe}</span>}
          </span>
          <h2 className={`t-intertitre ${styles.titreMessage}`}>
            <span className="visuellement-cache">{type} : </span>
            {titreCourt}
          </h2>
          <div className={`t-corps ${styles.corpsMessage}`}>{children}</div>
        </div>
      </div>
      {(correction || aide) && (
        <div className={styles.correction}>
          {correction && (
            <Bouton variante="secondaire" compact onClick={correction.onClick}>
              {correction.libelle}
            </Bouton>
          )}
          {aide && <span className="t-petit c-700">{aide}</span>}
        </div>
      )}
    </section>
  );
}

export function LienRetour({ vers, children }: { vers: string; children: ReactNode }) {
  return (
    <Link to={vers} className={styles.retour}>
      <Icone nom="fleche-gauche" taille={16} />
      <span>{children}</span>
    </Link>
  );
}

export function Section({ titre, droite, children, id, className }: { titre: ReactNode; droite?: ReactNode; children: ReactNode; id?: string; className?: string }) {
  return (
    <section className={`section ${styles.section} ${className ?? ''}`} aria-labelledby={id}>
      <div className={styles.enteteSection}>
        <h2 className="t-panneau" id={id}>{titre}</h2>
        {droite}
      </div>
      {children}
    </section>
  );
}
