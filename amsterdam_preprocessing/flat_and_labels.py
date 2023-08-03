from database_processing.flatandlabelsprocessor import FlatAndLabelsProcessor

import pandas as pd


def _translate_origin(series):
    return series.replace({
        'Verpleegafdeling zelfde ziekenhuis':
            'nursing department of the same hospital',
        'Eerste Hulp afdeling zelfde ziekenhuis':
            'emergency department of the same hospital',
        'CCU/IC zelfde ziekenhuis':
            'CCU/IC of the same hospital',
        'Special/Medium care zelfde ziekenhuis':
            'special/medium care from the same hospital',
        'Huis':
            'Home',
        'Recovery zelfde ziekenhuis (alleen bij niet geplande IC-opname)':
            'recovery from the same hospital (only in case of unplanned IC admission)',
        'Verpleegafdeling ander ziekenhuis':
            'nursing department from other hospital',
        'Special/Medium care ander ziekenhuis':
            'special/medium care from other hospital',
        'CCU/IC ander ziekenhuis':
            'CCU/IC from other hospital',
        'Eerste Hulp afdeling ander ziekenhuis':
            'emergency department from other hospital',
        'Recovery ander ziekenhuis':
            'recovery from other hospital',
        'Anders':
            'Other',
        'Operatiekamer vanaf verpleegafdeling zelfde ziekenhuis':
            'operating room from nuring ward of the same hospital',
        'Andere locatie zelfde ziekenhuis, transport per ambulance':
            'different location of the same hospital, transport by ambulance',
        'Operatiekamer vanaf Eerste Hulp afdeling zelfde ziekenhuis':
            'operating room from emergency department of the same hospital'
    })


class Ams_FLProcessor(FlatAndLabelsProcessor):
    def __init__(self):
        super().__init__(dataset='amsterdam')

        self.labels = self.load(f'{self.parquet_pth}/labels.parquet')
        self.flat = self.load(f'{self.parquet_pth}/labels.parquet',
                              columns=['admissionid',
                                       'urgency',
                                       'location',
                                       'origin',
                                       'gender',
                                       'agegroup',
                                       'weightgroup',
                                       'heightgroup',
                                       'specialty'])

        self.gender_mapping = {'Man': 1,
                               'Vrouw': 0,
                               'unknown': 0.5}

    def _decategorize(self, df, cols):
        def _dec(x):
            return str(x).replace('-', ' ').replace('+', ' ').split()[0]

        df[cols] = (df[cols].applymap(_dec)
                            .apply(pd.to_numeric, errors='coerce'))
        return df

    def preprocess_labels(self):
        labels = self.labels.loc[:, ['admissionid',
                                     'patientid',
                                     'admissioncount',
                                     'lengthofstay',
                                     'urgency',
                                     'gender',
                                     'agegroup',
                                     'weightgroup',
                                     'heightgroup',
                                     'specialty',
                                     'destination',
                                     'origin',
                                     'location']]

        labels[self.mor_col] = ((labels['destination'] == 'Overleden')
                                .astype(int))
        labels['gender'] = (labels.gender.fillna('unknown')
                                  .replace(self.gender_mapping))

        labels = self.harmonize_los(labels, 'lengthofstay', unit='hour')

        labels['raw_age'] = labels['agegroup']
        labels['raw_weight'] = labels['weightgroup']
        labels['raw_height'] = labels['heightgroup']

        cols_fill = ['agegroup', 'weightgroup', 'heightgroup']
        cols_num = cols_fill + ['raw_height', 'raw_weight']

        labels = (labels.pipe(self._decategorize, cols=cols_num)
                        .pipe(self.medianfill, cols=cols_fill)
                        .rename(columns={'admissionid': self.idx_col,
                                         'patientid': 'uniquepid',
                                         'gender': 'sex',
                                         'agegroup': 'age',
                                         'weightgroup': 'weight',
                                         'heightgroup': 'height',
                                         'specialty': 'unit_type'})
                  .set_index(self.idx_col)
                  .astype({'uniquepid': str})
                  .rename(columns={'destination': 'discharge_location'})
                  .sort_index())

        labels['origin'] = (labels['origin'].pipe(_translate_origin))
        labels['care_site'] = 'Amsterdam University Medical Center'
        return labels, self.flat

    def preprocess_flat(self):
        flat = self.flat

        cat = ['specialty', 'location', 'origin']
        num = ['agegroup', 'heightgroup', 'weightgroup']

        flat = (flat.fillna({'gender': 'unknown'})
                    .replace({'gender': self.gender_mapping})
                    .pipe(self.categorical_dummies, cols=cat)
                    .rename(columns={'admissionid': self.idx_col})
                    .set_index(self.idx_col)
                    .pipe(self._decategorize, cols=num)
                    .pipe(self.medianfill, cols=num))

        nunique = flat.nunique()
        scalecols = nunique[nunique > 2].index
        flat = (flat.pipe(self.clip_and_norm, cols=scalecols)
                    .sort_index())
        return flat
