/** Gabarit commun : bandeau de simulation, en-tête (logo, procédure, aide, menu de profil), contenu. */
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { MODE_DIRECT } from '../api/tribunal';
import { Icone } from './Icone';
import styles from './Gabarit.module.css';

export type EtapeProcedure = 'decision' | 'tribunal' | 'verdict';

const ETAPES: { id: EtapeProcedure; libelle: string }[] = [
  { id: 'decision', libelle: 'Décision' },
  { id: 'tribunal', libelle: 'Tribunal' },
  { id: 'verdict', libelle: 'Verdict' },
];

export function useTitre(ecran: string) {
  useEffect(() => {
    document.title = `Astrée · ${ecran}`;
  }, [ecran]);
}

export function BandeauSimulation() {
  return (
    <div className={styles.bandeau} role="note">
      <Icone nom="fiole" taille={13} />
      <span>Simulation · aucune transaction réelle · aucun conseil personnalisé</span>
    </div>
  );
}

/** Rang affiché au dernier écran : chaque écran remonte le gabarit, le curseur glisse depuis l'étape précédente. */
let dernierRang = 0;

function Procedure({ courante }: { courante: EtapeProcedure }) {
  const rang = ETAPES.findIndex((e) => e.id === courante);
  const [rangAffiche, setRangAffiche] = useState(dernierRang);
  useEffect(() => {
    const image = requestAnimationFrame(() => setRangAffiche(rang));
    dernierRang = rang;
    return () => cancelAnimationFrame(image);
  }, [rang]);
  return (
    <nav aria-label="Étapes de la procédure" style={{ '--rang': rangAffiche, '--nb-etapes': ETAPES.length } as React.CSSProperties}>
      <ol className={styles.procedure}>
        {ETAPES.map((etape, i) => {
          const etat = i < rang ? 'faite' : i === rang ? 'courante' : 'avenir';
          return (
            <li key={etape.id} className={`${styles.etape} ${styles[etat]}`} aria-current={etat === 'courante' ? 'step' : undefined}>
              <span className={styles.pastille} aria-hidden="true">
                {etat === 'faite' ? <Icone nom="check" taille={14} /> : i + 1}
              </span>
              <span>
                {etape.libelle}
                {etat === 'faite' && <span className="visuellement-cache"> (faite)</span>}
                {etat === 'avenir' && <span className="visuellement-cache"> (à venir)</span>}
              </span>
            </li>
          );
        })}
      </ol>
      <span className={styles.progression} aria-hidden="true" />
    </nav>
  );
}

function useFermetureExterieure(ouvert: boolean, fermer: () => void, refs: React.RefObject<HTMLElement>[]) {
  useEffect(() => {
    if (!ouvert) return undefined;
    const surClic = (e: MouseEvent) => {
      if (!refs.some((r) => r.current?.contains(e.target as Node))) fermer();
    };
    const surTouche = (e: KeyboardEvent) => {
      if (e.key === 'Escape') fermer();
    };
    document.addEventListener('mousedown', surClic);
    document.addEventListener('keydown', surTouche);
    return () => {
      document.removeEventListener('mousedown', surClic);
      document.removeEventListener('keydown', surTouche);
    };
  }, [ouvert, fermer, refs]);
}

function Aide() {
  const [ouvert, setOuvert] = useState(false);
  const bouton = useRef<HTMLButtonElement>(null);
  const panneau = useRef<HTMLDivElement>(null);
  const id = useId();
  const fermer = () => {
    setOuvert(false);
    bouton.current?.focus();
  };
  useFermetureExterieure(ouvert, fermer, [bouton, panneau]);
  return (
    <div className={styles.ancre}>
      <button ref={bouton} type="button" className={styles.outil} aria-expanded={ouvert} aria-controls={id} onClick={() => setOuvert((o) => !o)}>
        <Icone nom="aide" taille={18} />
        <span>Aide</span>
      </button>
      {ouvert && (
        <div ref={panneau} id={id} className={styles.panneauAide} role="dialog" aria-label="Aide">
          <p className="t-corps-fort">Comment fonctionne Astrée</p>
          <p className="t-petit">
            Vous soumettez une décision. Des agents Amazon Bedrock rassemblent des pièces calculées en Python : un Procureur
            plaide contre, un Avocat plaide pour, et le Greffier vérifie chaque chiffre cité et les règles de votre Pacte.
            C'est vous qui rendez le verdict.
          </p>
          <p className="t-petit c-500">
            Mode {MODE_DIRECT ? 'direct : le Tribunal est appelé sur AWS Lambda.' : 'démonstration : des procès réellement tenus par les agents sont rejoués.'}
          </p>
        </div>
      )}
    </div>
  );
}

function MenuProfil({ nom }: { nom: string }) {
  const [ouvert, setOuvert] = useState(false);
  const bouton = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLUListElement>(null);
  const navigate = useNavigate();
  const id = useId();
  const fermer = () => {
    setOuvert(false);
    bouton.current?.focus();
  };
  useFermetureExterieure(ouvert, fermer, [bouton, menu]);
  useEffect(() => {
    if (ouvert) menu.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
  }, [ouvert]);
  return (
    <div className={styles.ancre}>
      <button
        ref={bouton}
        type="button"
        className={styles.menuProfil}
        aria-haspopup="menu"
        aria-expanded={ouvert}
        aria-controls={id}
        onClick={() => setOuvert((o) => !o)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            setOuvert(true);
          }
        }}
      >
        <span className={styles.avatar} aria-hidden="true">{nom.charAt(0)}</span>
        <span>{nom}</span>
        <span className="visuellement-cache">, menu du profil</span>
        <Icone nom="chevron-bas" taille={14} />
      </button>
      {ouvert && (
        <ul ref={menu} id={id} role="menu" className={styles.menu} aria-label="Profil">
          <li role="none">
            <button
              type="button"
              role="menuitem"
              className={styles.elementMenu}
              onClick={() => {
                setOuvert(false);
                navigate('/');
              }}
            >
              Changer de profil
            </button>
          </li>
        </ul>
      )}
    </div>
  );
}

/** `inert` n'est pas encore typé par React 18 : on le passe comme attribut HTML brut. */
export function attributInerte(inerte: boolean): Record<string, string> {
  return inerte ? { inert: '' } : {};
}

interface ProprietesGabarit {
  children: ReactNode;
  nomProfil?: string;
  idProfil?: string;
  etape?: EtapeProcedure;
  /** Superposition (tiroir) : le contenu principal devient inerte. */
  inerte?: boolean;
}

export function Gabarit({ children, nomProfil, idProfil, etape, inerte = false }: ProprietesGabarit) {
  return (
    <div className={styles.page}>
      <header className={styles.haut} {...attributInerte(inerte)}>
        <a className={styles.evitement} href="#contenu">Aller au contenu</a>
        <BandeauSimulation />
        <div className={styles.entete}>
          <Link to={idProfil ? `/${idProfil}/portefeuille` : '/'} className={styles.logo} aria-label={idProfil ? 'Astrée, retour au portefeuille' : 'Astrée, accueil'}>
            <span className={styles.marque}>
              <img src={`${import.meta.env.BASE_URL}marque.svg`} width={30} height={30} alt="" />
            </span>
            <span className={styles.nomMarque}>
              <span className={styles.motMarque}>Astrée</span>
              <span className={styles.devise}>Tribunal des décisions</span>
            </span>
          </Link>
          {etape && <Procedure courante={etape} />}
          <div className={styles.outils}>
            <Aide />
            {nomProfil && <MenuProfil nom={nomProfil} />}
          </div>
        </div>
      </header>
      <main id="contenu" className={styles.contenu} {...attributInerte(inerte)} tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}
