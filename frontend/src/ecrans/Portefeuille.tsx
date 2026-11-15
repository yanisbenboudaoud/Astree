/** Écran Portefeuille (annexe D.2), avec la recherche (D.3) et la confirmation après signature (C.6). */
import { useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import type { EntreeJournal, Profil } from '../api/types';
import { configUi, nomTitre } from '../api/donnees';
import { Gabarit, useTitre } from '../components/Gabarit';
import { GraphiqueValeur } from '../components/graphiques/GraphiqueValeur';
import { Recherche } from '../components/Recherche';
import { Bouton } from '../components/Bouton';
import { IconeStatut, Provenance, Statut } from '../components/Etiquettes';
import { Jauge, Monogramme, Section } from '../components/Elements';
import { Icone } from '../components/Icone';
import { compte, date, dollars, jourMois, part, pourcent } from '../lib/format';
import { bilanPacte, regleCle, seuilPireBaisse, statutUi, valeurRegle } from '../domaine/pacte';
import { useEtatProfil } from '../state/store';
import styles from './Portefeuille.module.css';

const TEINTES = ['var(--encre-900)', 'var(--encre-700)', 'var(--encre-500)', 'var(--encre-300)', 'var(--trait-moyen)', 'var(--trait-fin)'];
const TEINTES_COURTES = ['var(--encre-900)', 'var(--encre-500)', 'var(--encre-300)'];

function Indicateurs({ profil }: { profil: Profil }) {
  const seuil = seuilPireBaisse(profil);
  const annees = Math.round((Date.parse(profil.fin) - Date.parse(profil.debut)) / 3.15576e10);
  const utilisation = seuil ? profil.actuel.chuteMax / seuil : null;
  return (
    <dl className={styles.indicateurs}>
      <div className={styles.indicateur}>
        <dt className="t-petit-fort c-500">Rendement annualisé</dt>
        <dd className="t-chiffre-moyen">{pourcent(profil.actuel.rendement, { signe: true })}</dd>
        <dd className="t-petit c-500">par an sur {annees} ans</dd>
      </div>
      <div className={styles.indicateur}>
        <dt className="t-petit-fort c-500">Chute maximale</dt>
        <dd className="t-chiffre-moyen">{pourcent(profil.actuel.chuteMax)}</dd>
        {seuil !== undefined && utilisation !== null && (
          <>
            <dd className={styles.jaugeIndicateur}>
              <Jauge valeur={utilisation} libelle={`Chute maximale : ${pourcent(utilisation, { decimales: 0 })} de la limite de votre Pacte`} />
            </dd>
            <dd className="t-petit c-500">{pourcent(utilisation, { decimales: 0 })} de votre limite de {pourcent(seuil, { decimales: 0 })}</dd>
          </>
        )}
      </div>
      <div className={styles.indicateur}>
        <dt className="t-petit-fort c-500">Volatilité</dt>
        <dd className="t-chiffre-moyen">{pourcent(profil.actuel.volatilite)}</dd>
        <dd className="t-petit c-500">annualisée</dd>
      </div>
    </dl>
  );
}

function Positions({ profil }: { profil: Profil }) {
  const teintes = profil.groupes.length <= 3 ? TEINTES_COURTES : TEINTES;
  const teinte = (groupe: string) => teintes[profil.groupes.findIndex((g) => g.libelle === groupe) % teintes.length];
  return (
    <Section
      id="titre-positions"
      titre="Vos positions"
      droite={(
        <span className={styles.groupeDroite}>
          <span className="t-petit c-500">{compte(profil.positions.length, 'titre')}</span>
          <Provenance type="Fictif" />
        </span>
      )}
    >
      <div className={styles.repartition} aria-hidden="true">
        {profil.groupes.map((g) => (
          <span key={g.libelle} style={{ flexGrow: g.poids, background: teinte(g.libelle) }} />
        ))}
      </div>
      <ul className={styles.legende} aria-label="Répartition par groupe">
        {profil.groupes.map((g) => (
          <li key={g.libelle}>
            <span className={styles.carre} style={{ background: teinte(g.libelle) }} aria-hidden="true" />
            <span className="t-petit c-700">{g.libelle}</span>
            <span className="t-tableau-fort">{part(g.poids)}</span>
          </li>
        ))}
      </ul>
      <ul className={styles.liste}>
        {profil.positions.map((p) => (
          <li key={p.ticker} className={styles.ligne}>
            <Monogramme ticker={p.ticker} />
            <span className={styles.nom}>
              <span className="t-corps">{nomTitre(p.ticker)}</span>
              <span className="t-petit c-500">{p.ticker} · {p.groupe}</span>
            </span>
            <span className={`t-tableau ${styles.montantLigne}`}>{dollars(p.valeur)}</span>
            <span className={`t-tableau-fort ${styles.poids}`}>{part(p.poids)}</span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

function CartePacte({ profil }: { profil: Profil }) {
  const [ouvert, setOuvert] = useState(false);
  const cle = regleCle(profil);
  const bilan = bilanPacte(profil);
  const regles = profil.pacte.regles;
  const detail = [cle ? valeurRegle(cle) : null, `${compte(bilan.verifiees, 'règle vérifiée', 'règles vérifiées')}`, bilan.aJuger ? `${bilan.aJuger} à juger par vous` : null]
    .filter(Boolean).join(' · ');
  return (
    <section className={styles.cartePacte} aria-labelledby="titre-pacte">
      <div className={styles.entetePacte}>
        <h2 className="t-panneau" id="titre-pacte">Votre Pacte</h2>
        <Statut type={bilan.statut} />
      </div>
      {cle && (
        <div className={styles.regleCle}>
          <p className="t-corps-fort">{cle.libelle}</p>
          <Jauge valeur={cle.utilisation ?? 0} libelle={`${cle.libelle} : ${pourcent(cle.utilisation ?? 0, { decimales: 0 })} de la limite utilisée`} />
        </div>
      )}
      <p className="t-petit c-500">{detail}</p>
      <Bouton variante="tertiaire" compact fleche={false} aria-expanded={ouvert} aria-controls="regles-pacte" onClick={() => setOuvert((o) => !o)} className={styles.voirRegles}>
        {ouvert ? 'Masquer les règles' : `Voir les ${regles.length} règles`}
      </Bouton>
      <ol id="regles-pacte" className={styles.regles} hidden={!ouvert}>
        {regles.map((r, i) => (
          <li key={r.id}>
            <span className="t-trace c-500">§{i + 1}</span>
            <span className="t-petit">{r.libelle}</span>
            <IconeStatut type={statutUi(r.statut)} taille={14} />
          </li>
        ))}
        <li className="t-petit c-500">Signé le {date(profil.pacte.dateSignature)}. Les règles sans calcul possible sont à juger par vous.</li>
      </ol>
    </section>
  );
}

function Journal({ entrees }: { entrees: EntreeJournal[] }) {
  const [tout, setTout] = useState(false);
  const visibles = tout ? entrees : entrees.slice(0, 3);
  return (
    <section className={`section ${styles.journal}`} aria-labelledby="titre-journal">
      <div className={styles.enteteJournal}>
        <h2 className="t-panneau" id="titre-journal">Journal des décisions</h2>
        {entrees.length > 3 && (
          <Bouton variante="tertiaire" compact fleche={false} aria-expanded={tout} onClick={() => setTout((t) => !t)}>
            {tout ? 'Réduire' : 'Tout voir'}
          </Bouton>
        )}
      </div>
      <ul>
        {visibles.map((e) => (
          <li key={`${e.date}-${e.texte}`} className={`${styles.entree} ${e.nouveau ? styles.entreeNouvelle : ''}`}>
            <span className={`t-trace c-500 ${styles.dateJournal}`}>{jourMois(e.date)}</span>
            <span className="t-corps">{e.texte}</span>
            <IconeStatut type={statutUi(e.statut)} />
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Portefeuille({ profil }: { profil: Profil }) {
  useTitre('Portefeuille');
  const navigate = useNavigate();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const config = configUi(profil.id);
  const { etat, definirDecision, definirPanier, annulerSignature } = useEtatProfil(profil.id);
  const bilan = bilanPacte(profil);
  const archive = params.get('archive') === '1' && etat.archive;
  const journal = [...etat.journal, ...(config.journal ?? [])];
  const focusRecherche = Boolean((location.state as { recherche?: boolean } | null)?.recherche);

  const instruire = (ticker: string) => {
    const defaut = profil.decisionDemo?.type === 'position' && profil.decisionDemo.ticker === ticker
      ? Math.round(profil.decisionDemo.taille * 100) : 10;
    const enCours = etat.decision?.type === 'position' && etat.decision.ticker === ticker ? etat.decision.taille : defaut;
    definirDecision({ type: 'position', ticker, taille: enCours });
    navigate(`/${profil.id}/decision`);
  };

  const instruirePanier = () => {
    const n = etat.panier.length;
    const base = Math.floor(100 / n / 5) * 5;
    const lignes = etat.panier.map((ticker, i) => ({ ticker, poids: i === 0 ? 100 - base * (n - 1) : base }));
    definirDecision({ type: 'panier', lignes });
    navigate(`/${profil.id}/decision`);
  };

  return (
    <Gabarit nomProfil={profil.nom} idProfil={profil.id}>
      <div className={styles.corps}>
        {archive && (
          <div className={styles.archive} role="status">
            <Icone nom="check" taille={18} />
            <div className={styles.texteArchive}>
              <p className="t-corps-fort">Verdict signé et archivé</p>
              <p className="t-petit">{etat.archive!.resume}</p>
            </div>
            <button
              type="button"
              className={styles.annulerSignature}
              onClick={() => {
                annulerSignature();
                params.delete('archive');
                setParams(params, { replace: true });
              }}
            >
              <Icone nom="annuler" taille={16} />
              Annuler la signature
            </button>
          </div>
        )}

        <div className={styles.titre}>
          <h1 className="t-h1">Bonjour {profil.nom}.</h1>
          <p className={styles.statut}>
            <span className={bilan.violations ? styles.iconeViolation : styles.iconeConforme}>
              <Icone nom={bilan.violations ? 'interdit' : 'check'} taille={18} />
            </span>
            <span className="t-corps c-700">
              {bilan.violations
                ? `Votre portefeuille enfreint ${compte(bilan.violations, 'règle')} de votre Pacte.`
                : 'Votre portefeuille respecte les règles mesurables de votre Pacte.'}
            </span>
          </p>
        </div>

        <div className={styles.grille}>
          <div className={styles.principale}>
            <section className={`section ${styles.valeur}`} aria-labelledby="titre-valeur">
              <div className={styles.montant}>
                <div className={styles.blocValeur}>
                  <h2 className="t-petit-fort c-500" id="titre-valeur">Valeur du portefeuille</h2>
                  <p className={styles.chiffre}>
                    <span className="t-affiche">{dollars(profil.capital)}</span>
                    <Provenance type="Fictif" />
                  </p>
                  <p className={styles.variation}>
                    <span className="t-tableau-fort">
                      <span aria-hidden="true">{profil.actuel.gain >= 0 ? '▲' : '▼'}</span>
                      <span className="visuellement-cache">{profil.actuel.gain >= 0 ? 'Hausse de ' : 'Baisse de '}</span>
                      {' '}{dollars(Math.abs(profil.actuel.gain))}
                    </span>
                    <span className="t-tableau">({pourcent(profil.actuel.gainPct, { signe: true })})</span>
                    <span className="t-petit c-500">depuis le {date(profil.debut)}</span>
                  </p>
                </div>
                <p className="t-petit-fort c-500">Sur {Math.round((Date.parse(profil.fin) - Date.parse(profil.debut)) / 3.15576e10)} ans</p>
              </div>
              <GraphiqueValeur
                serie={profil.serieValeur}
                pointBas={{ date: profil.actuel.dateChuteMax, valeur: profil.actuel.valeurChuteMax, recul: profil.actuel.chuteMax }}
              />
              <Indicateurs profil={profil} />
              <p className={styles.provenance}>
                <Provenance type="Fait" />
                <span className="t-petit c-500">Calculé sur les prix réels du {date(profil.debut)} au {date(profil.fin)}, en CAD.</span>
              </p>
            </section>
            <Positions profil={profil} />
          </div>

          <aside className={styles.laterale} aria-label="Décision, Pacte et journal">
            <Recherche
              profil={profil}
              mode={config.recherche.mode}
              titre={config.recherche.titre}
              aide={config.recherche.aide}
              placeholder={config.recherche.placeholder}
              panier={etat.panier}
              onInstruire={instruire}
              onPanier={definirPanier}
              onInstruirePanier={instruirePanier}
              focusInitial={focusRecherche}
            />
            <CartePacte profil={profil} />
            <Journal entrees={journal} />
          </aside>
        </div>
      </div>
    </Gabarit>
  );
}
