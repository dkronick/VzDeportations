
********************************************************************************
* ICE arrests of Venezuelans
********************************************************************************

* load arrest data
import delimited "arrests-latest.csv", varnames(1) clear 

* date 
gen int apprehension_d = date(apprehension_date, "YMD")
format apprehension_d %td 
gen week = wofd(apprehension_d)
format week %tw

* Venezuelans
keep if citizenship_country == "VENEZUELA"

* count
gen arrests = 1 /* To sum this up */
replace arrests = 0.5 if duplicate_likely == 1

collapse (sum) arrests, by(week)

twoway bar arrests week if week >= wofd(td(01sep2024))

********************************************************************************
* End of do file
********************************************************************************
