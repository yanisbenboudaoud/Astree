/**
 * Écran Verdict (annexe C.6). L'utilisateur tranche ; « Signer le verdict » n'exécute rien,
 * il archive le choix (POST /verdict en mode direct, journal local en démonstration).
 */
import { useId, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import type { Profil } from '../api/types';
import { archiverVerdict, ouvrirProcesVerbal } from '../api/tribunal';
import { Gabarit, useTitre } from '../components/Gabarit';
import { Bouton } from '../components/Bouton';
import { Statut } from '../components/Etiquettes';
import { LienRetour, Message } from '../components/Elements';
import { OPTION_PACTE, archivage, optionsVerdict, pointsDeBascule, statutDecision, type OptionVerdict } from '../domaine/verdict';
import { useEtatProfil } from '../state/store';
import { useTables } from '../state/useTables';
import styles from './Verdict.module.css';

const LONGUEUR_MAX = 280;

function aujourdhui(): string {
  return new Date().toLocaleDateString('en-CA');
}

export function Verdict({ profil }: { profil: Profil }) {
  useTitre('Verdict');
  const navigate = useNavigate();
  const { etat, modifierVerdict, signer } = useEtatProfil(profil.id);
  const { decision, tribunal, verdict } = etat;
  const { tablePosition, entree } = useTables(profil, decision);
  const [erreur, setErreur] = useState<string | null>(null);
  const [erreurExport, setErreurExport] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);
  const idRaison = useId();
  const idJustification = useId();
  const idCompteur = useId();
  const idBascule = useId();

  if (!decision || tribunal.statut !== 'pret' || !tribunal.resultat) return <Navigate to={`/${profil.id}/tribunal`} replace />;
  const resultat = tribunal.resultat;
  const options = optionsVerdict({ profil, resultat, decision, table: tablePosition, entreeDecision: entree });
  const toutes = [...options, OPTION_PACTE];
  const choisie: OptionVerdict | undefined = toutes.find((o) => o.id === verdict.option);
  const statut = statutDecision(profil, resultat);
  const violations = resultat.controles.filter((c) => c.paragraphe !== undefined && c.statut === 'Violation').length;
  const bascules = pointsDeBascule(resultat);

  const raisonBlocage = !choisie
    ? 'Choisissez une option pour signer le verdict.'
    : choisie.engagement && (!verdict.justification.trim() || !verdict.compris)
      ? 'Pour maintenir malgré la violation, écrivez pourquoi et cochez la case : la signature reste désactivée jusque-là.'
      : null;

  const exporterProcesVerbal = async () => {
    setErreurExport(null);
    try {
      await ouvrirProcesVerbal(resultat.procesId);
    } catch (e) {
      setErreurExport(e instanceof Error ? e.message : String(e));
    }
  };

  const signerVerdict = async () => {
    if (raisonBlocage || !choisie) return;
    setEnvoi(true);
    setErreur(null);
    try {
      await archiverVerdict(resultat.procesId, choisie.verdict);
      const { resume, journal, statut: statutJournal } = archivage(choisie, decision, violations);
      signer(resume, { date: aujourdhui(), texte: journal, statut: statutJournal });
      navigate(`/${profil.id}/portefeuille?archive=1`);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
      setEnvoi(false);
    }
  };

  const carte = (option: OptionVerdict) => {
    const selectionnee = verdict.option === option.id;
    return (
      <li key={option.id} className={`${styles.option} ${selectionnee ? styles.selectionnee : ''}`}>
        <label className={styles.etiquetteOption}>
          <input
            type="radio"
            name="verdict"
            value={option.id}
            checked={selectionnee}
            onChange={() => modifierVerdict({ option: option.id })}
            className={styles.radio}
          />
          <span className={styles.texteOption}>
            <span className={styles.ligneTitre}>
              <span className="t-corps-fort">{option.titre}</span>
              {option.statut && <Statut type={option.statut} />}
            </span>
            <span className="t-petit c-700">{option.sousTitre}</span>
            {option.mesures.length > 0 && (
              <span className={styles.mesures}>
                {option.mesures.map((m) => (
                  <span key={m.libelle}>
                    <span className="t-petit c-500">{m.libelle}</span>{' '}
                    <span className="t-tableau-fort">{m.valeur}</span>
                  </span>
                ))}
              </span>
            )}
          </span>
        </label>
        {selectionnee && option.engagement && (
          <div className={styles.engagement}>
            <label htmlFor={idJustification} className={styles.libelleJustification}>
              <span className="t-corps-fort">Pourquoi maintenir malgré la violation ?</span>
              <span className="t-petit c-500"> obligatoire</span>
            </label>
            <div className={styles.zoneTexte}>
              <textarea
                id={idJustification}
                maxLength={LONGUEUR_MAX}
                rows={2}
                required
                aria-required="true"
                aria-describedby={idCompteur}
                value={verdict.justification}
                onChange={(e) => modifierVerdict({ justification: e.target.value })}
              />
              <span id={idCompteur} className="t-petit c-500">{verdict.justification.length} / {LONGUEUR_MAX} caractères</span>
            </div>
            <label className={styles.case}>
              <input type="checkbox" checked={verdict.compris} required onChange={(e) => modifierVerdict({ compris: e.target.checked })} />
              <span className="t-petit">{option.engagement}</span>
            </label>
          </div>
        )}
        {selectionnee && option.noteSiChoisie && <p className={`t-petit ${styles.note}`}>{option.noteSiChoisie}</p>}
      </li>
    );
  };

  return (
    <Gabarit nomProfil={profil.nom} idProfil={profil.id} etape="verdict">
      <div className={styles.corps}>
        <LienRetour vers={`/${profil.id}/tribunal`}>Tribunal</LienRetour>
        <div className={styles.titre}>
          <p className="t-etiquette c-500">Verdict</p>
          <h1 className="t-h1">Quelle est votre décision ?</h1>
          <p className={styles.rappel}>
            <Statut type={statut} />
            <span className="t-corps c-700">{resultat.constat}</span>
          </p>
        </div>

        {bascules.length > 0 && (
          <section className={styles.bascule} aria-labelledby={idBascule}>
            <h2 id={idBascule} className="t-etiquette c-500">Ce qui changerait la réponse</h2>
            <ul>
              {bascules.map((p) => (
                <li key={p.regle} className={styles.point}>
                  <span className="t-petit-fort">{p.paragraphe ? `§${p.paragraphe} · ` : ''}{p.libelle}</span>
                  <span className="t-petit c-700">
                    {p.message}
                    {p.pieces.map((code) => (
                      <span key={code}>
                        {' '}
                        <Link to={`/${profil.id}/tribunal?piece=${code}`} className={styles.lienPiece} aria-label={`Ouvrir la pièce ${code}`}>{code}</Link>
                      </span>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <fieldset className={styles.options}>
          <legend className="visuellement-cache">Votre décision sur « {resultat.titre} »</legend>
          <ul>
            {options.map(carte)}
            {verdict.option === 'pacte' && carte(OPTION_PACTE)}
          </ul>
        </fieldset>

        {verdict.option !== 'pacte' && (
          <Bouton variante="tertiaire" compact fleche={false} className={styles.lienPacte} onClick={() => modifierVerdict({ option: 'pacte' })}>
            Ou ajuster votre Pacte avant de décider
          </Bouton>
        )}

        {erreur && (
          <Message type="Violation" titre="Le verdict n'a pas pu être archivé" correction={{ libelle: 'Réessayer', onClick: signerVerdict }}>
            <p>{erreur}</p>
          </Message>
        )}

        <p className={`t-petit c-700 ${styles.export}`}>
          <Bouton variante="tertiaire" compact fleche={false} className={styles.lienExport} onClick={exporterProcesVerbal}>
            Exporter le procès-verbal
          </Bouton>{' '}
          : tout le dossier du procès (pièces, contrôles, arguments, trace), en page imprimable.
        </p>

        {erreurExport && (
          <Message type="Violation" titre="Le procès-verbal n'a pas pu être produit" correction={{ libelle: 'Réessayer', onClick: exporterProcesVerbal }}>
            <p>{erreurExport}</p>
          </Message>
        )}

        <div className={styles.actions}>
          <Bouton variante="tertiaire" fleche={false} vers={`/${profil.id}/tribunal`}>Retour au Tribunal</Bouton>
          <div className={styles.signature}>
            <p className="t-petit c-700">Rien n'est exécuté : le verdict est archivé.</p>
            <Bouton
              variante="primaire"
              onClick={signerVerdict}
              aria-disabled={Boolean(raisonBlocage) || envoi || undefined}
              aria-describedby={raisonBlocage ? idRaison : undefined}
            >
              {envoi ? 'Archivage…' : 'Signer le verdict'}
            </Bouton>
          </div>
        </div>
        {raisonBlocage && <p id={idRaison} className={`t-petit c-700 ${styles.raison}`}>{raisonBlocage}</p>}
      </div>
    </Gabarit>
  );
}
