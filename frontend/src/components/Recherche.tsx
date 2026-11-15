/**
 * Recherche d'actifs (annexe D.3) : combobox ARIA sur les 31 titres de l'univers.
 * ↑ ↓ pour parcourir, Entrée pour instruire (ou ajouter au panier), Échap pour fermer.
 * Les signalements (exclusion, plafond, critère documentaire) viennent du Pacte du profil.
 */
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import type { Profil, Titre } from '../api/types';
import { TITRES, nomTitre } from '../api/donnees';
import { rechercherTitres, type ResultatRecherche } from '../lib/recherche';
import { pourcent, tickerCourt } from '../lib/format';
import { signalementsTitre } from '../domaine/pacte';
import { Provenance, Statut } from './Etiquettes';
import { Icone } from './Icone';
import { Monogramme } from './Elements';
import { Bouton } from './Bouton';
import styles from './Recherche.module.css';

interface ProprietesRecherche {
  profil: Profil;
  mode: 'position' | 'panier';
  titre: string;
  aide: string;
  placeholder: string;
  panier: string[];
  onInstruire: (ticker: string) => void;
  onPanier: (tickers: string[]) => void;
  onInstruirePanier: () => void;
  focusInitial?: boolean;
}

function NomSurligne({ resultat }: { resultat: ResultatRecherche }) {
  const { titre, surligne } = resultat;
  if (!surligne) return <>{titre.nom}</>;
  const { debut, longueur } = surligne;
  return (
    <>
      {titre.nom.slice(0, debut)}
      <strong>{titre.nom.slice(debut, debut + longueur)}</strong>
      {titre.nom.slice(debut + longueur)}
    </>
  );
}

export function Recherche({ profil, mode, titre, aide, placeholder, panier, onInstruire, onPanier, onInstruirePanier, focusInitial }: ProprietesRecherche) {
  const [requete, setRequete] = useState('');
  const [ouvert, setOuvert] = useState(false);
  const [actif, setActif] = useState(0);
  const champ = useRef<HTMLInputElement>(null);
  const idListe = useId();
  const idAide = useId();
  const idTitre = useId();
  const resultats = useMemo(() => rechercherTitres(TITRES, requete), [requete]);
  const visible = ouvert && requete.trim().length > 0;
  const enPanier = mode === 'panier';

  useEffect(() => {
    if (focusInitial) champ.current?.focus();
  }, [focusInitial]);

  useEffect(() => setActif(0), [requete]);

  const choisir = (t: Titre) => {
    if (enPanier) {
      if (!panier.includes(t.ticker)) onPanier([...panier, t.ticker]);
      setRequete('');
      setOuvert(false);
      champ.current?.focus();
    } else {
      onInstruire(t.ticker);
    }
  };

  const surTouche = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setOuvert(true);
      setActif((a) => Math.min(a + 1, Math.max(resultats.length - 1, 0)));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActif((a) => Math.max(a - 1, 0));
    } else if (e.key === 'Enter') {
      if (visible && resultats[actif]) {
        e.preventDefault();
        choisir(resultats[actif].titre);
      }
    } else if (e.key === 'Escape') {
      if (visible) {
        e.preventDefault();
        setOuvert(false);
      } else setRequete('');
    }
  };

  const idOption = (i: number) => `${idListe}-option-${i}`;
  const titreActif = resultats[actif]?.titre;

  return (
    <section className={styles.carte} aria-labelledby={idTitre}>
      <h2 id={idTitre} className="t-h2">{titre}</h2>
      <p id={idAide} className={`t-petit ${styles.aide}`}>{aide}</p>

      {enPanier && panier.length > 0 && (
        <div className={styles.panier}>
          <p className="t-petit-fort">Dans votre panier · {panier.length} titre{panier.length > 1 ? 's' : ''}</p>
          <ul className={styles.pastilles}>
            {panier.map((t) => (
              <li key={t} className={styles.pastille}>
                <span>{tickerCourt(t)}</span>
                <button type="button" className={styles.retirer} aria-label={`Retirer ${nomTitre(t)} du panier`} onClick={() => onPanier(panier.filter((x) => x !== t))}>
                  <Icone nom="croix" taille={12} />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className={styles.zoneChamp}>
        <div className={`${styles.champ} ${visible ? styles.champOuvert : ''}`}>
          <Icone nom="recherche" taille={18} />
          <input
            ref={champ}
            type="text"
            role="combobox"
            aria-expanded={visible}
            aria-controls={idListe}
            aria-autocomplete="list"
            aria-activedescendant={visible && resultats.length ? idOption(actif) : undefined}
            aria-describedby={idAide}
            aria-label={enPanier ? 'Ajouter un titre au panier' : 'Chercher un titre à tester'}
            placeholder={placeholder}
            value={requete}
            autoComplete="off"
            spellCheck={false}
            onChange={(e) => {
              setRequete(e.target.value);
              setOuvert(true);
            }}
            onFocus={() => setOuvert(true)}
            onBlur={() => setTimeout(() => setOuvert(false), 150)}
            onKeyDown={surTouche}
          />
          {requete && (
            <button type="button" className={styles.effacer} aria-label="Effacer la recherche" onClick={() => { setRequete(''); champ.current?.focus(); }}>
              <Icone nom="croix" taille={14} />
            </button>
          )}
        </div>

        <div className={styles.couche} hidden={!visible}>
          <p className={`t-petit c-500 ${styles.enteteListe}`} aria-live="polite">
            {resultats.length
              ? `${resultats.length} résultat${resultats.length > 1 ? 's' : ''} pour « ${requete.trim()} »`
              : `Aucun titre ne correspond à « ${requete.trim()} » parmi les ${TITRES.length} titres de l'univers.`}
          </p>
          <ul id={idListe} role="listbox" aria-label="Titres de l'univers" className={styles.liste}>
            {resultats.map((r, i) => {
              const dejaDansPanier = enPanier && panier.includes(r.titre.ticker);
              const signalements = signalementsTitre(profil, r.titre);
              return (
                <li
                  key={r.titre.ticker}
                  id={idOption(i)}
                  role="option"
                  aria-selected={i === actif}
                  aria-disabled={dejaDansPanier || undefined}
                  className={`${styles.option} ${i === actif ? styles.optionActive : ''}`}
                  onMouseDown={(e) => e.preventDefault()}
                  onMouseEnter={() => setActif(i)}
                  onClick={() => !dejaDansPanier && choisir(r.titre)}
                >
                  <Monogramme ticker={r.titre.ticker} />
                  <span className={styles.description}>
                    <span className="t-corps"><NomSurligne resultat={r} /></span>
                    <span className="t-petit c-700">
                      {[r.titre.ticker, r.titre.classe, r.titre.bourse, r.titre.devise, r.titre.secteur].join(' · ')}
                    </span>
                    {signalements.map((s) => (
                      <span key={s.texte} className={styles.signalement}>
                        {s.statut ? <Statut type={s.statut} /> : s.provenance && <Provenance type={s.provenance} />}
                        <span className="t-petit c-700">{s.texte}</span>
                      </span>
                    ))}
                  </span>
                  {enPanier ? (
                    <span className={`${styles.ajouter} ${dejaDansPanier ? styles.ajoute : ''}`} aria-hidden="true">
                      {dejaDansPanier ? 'Dans le panier' : <><Icone nom="plus" taille={14} /> Ajouter</>}
                    </span>
                  ) : (
                    <span className={styles.volatilite}>
                      <span className="t-tableau-fort">≈ {pourcent(r.titre.volatilite, { decimales: 0 })}</span>
                      <span className="t-petit c-700">volatilité</span>
                    </span>
                  )}
                  {enPanier && <span className="visuellement-cache">{dejaDansPanier ? ', déjà dans le panier' : ', ajouter au panier'}</span>}
                </li>
              );
            })}
          </ul>
          <p className={`t-petit c-700 ${styles.piedListe}`}>
            {enPanier && titreActif && !panier.includes(titreActif.ticker)
              ? `Ajoutez ${titreActif.nom} pour instruire un panier de ${panier.length + 1} titre${panier.length + 1 > 1 ? 's' : ''}`
              : (
                <>
                  <kbd>↑ ↓</kbd> parcourir <kbd>Entrée</kbd> {enPanier ? 'ajouter' : 'instruire'} <kbd>Échap</kbd> fermer
                </>
              )}
          </p>
        </div>
      </div>

      {enPanier && panier.length >= 2 && (
        <Bouton variante="inverse" fleche onClick={onInstruirePanier}>
          Instruire le panier ({panier.length} titres)
        </Bouton>
      )}
      {enPanier && panier.length === 1 && <p className={`t-petit ${styles.aide}`}>Ajoutez au moins un autre titre pour instruire le panier.</p>}
    </section>
  );
}
