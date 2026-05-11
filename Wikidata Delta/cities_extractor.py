import pandas as pd
import re
import numpy as np
import os
from pathlib import Path

def cities_extractor(df):
    base_dir = Path(__file__).parent
    cities_file = base_dir / 'Cleaned all_data_worldcities.xlsx'
    df_cities = pd.read_excel(cities_file)    
    cities_list = df_cities['city'].str.lower().to_list()

    df_cities.replace(np.nan,'',regex = True, inplace = True)

    cities_list = sorted(cities_list, key=len, reverse=True)
    pattern = re.compile(fr"\b({'|'.join(map(re.escape, cities_list))})\b")

    def address_filter(address,city):

        temp_city = []
        if address == []:
            pass

        else:
            if city == []:
                for add in address:
                    if add:
                        matches = list(set(match for match in pattern.findall(add.lower())))
                        temp_city.extend(matches)
                        temp_city = list(set(temp_city))
                    else:
                        pass

            else:
                for add in address:
                    if add:
                        matches = list(set(match for match in pattern.findall(add.lower())))
                        temp_city.extend(matches)
                        temp_city = list(set(temp_city))
                    else:
                        pass

    #     city_remove_duplicate = []
    #     for c in city:
    #         if c.title().strip() in city_remove_duplicate:
    #             pass
    #         else:
    #             city_remove_duplicate.append(c.title().strip())

    #     return city_remove_duplicate
        city.extend(temp_city)
        return city

    df['City'] = df.apply(lambda row: address_filter(row['Primary Address'],row['City']),axis=1)

    return df