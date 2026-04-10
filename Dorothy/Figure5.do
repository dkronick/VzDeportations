
********************************************************************************
* Save ICE arrests so as to identify *interior* removals
********************************************************************************

* arrests (to identify interior arrests)
import delimited "arrests-latest.csv", varnames(1) clear 
keep unique_identifier
duplicates drop /* This isn't QUITE right because a person could be arrested after a border deportation? But that'll be a tiny fraction */
rename unique_identifier anonymizedidentifier
gen inarrestsdata = 1
tempfile arrestees 
save `arrestees' 

********************************************************************************
* Load removals data
********************************************************************************

* removals: 2025 
import delimited "2026-ICLI-00005_Removals_FY25_20260311_Redacted.csv", ///
	   varnames(7) rowrange(7) clear 
tempfile file2025
save `file2025'	   
	   	   
* removals: 2026
import delimited "2026-ICLI-00005_Removals_FY26_20260311_Redacted.csv", ///
	   varnames(7) rowrange(7) clear 
	   
* add 2025
append using `file2025'
duplicates drop

********************************************************************************
* Merge ICE arrests so as to distinguish interior from border removals
********************************************************************************

* identify interior removals
drop if anonymizedidentifier == ""
merge m:1 anonymizedidentifier using `arrestees'
drop if _m == 2 
drop _m 

* counts
gen totalremovals = 1
rename inarrestsdata interiorremovals


********************************************************************************
* Keep only Venezuelans
********************************************************************************

* country of origin
keep if citizenshipcountry == "VENEZUELA"


********************************************************************************
* TPS eligibility
********************************************************************************

* count of observations per person
* Note, ~98% of people only appear once
duplicates tag anonymizedidentifier, gen(obs_perperson)
replace obs_perperson = obs_perperson + 1 /* tag starts with zero */
drop if obs_perperson > 3 /* Nine Venezuelans */

* dates  
gen int departed_d = date(substr(departeddate,1,10), "YMD")
format departed_d %td
gen int entrydate_d = date(substr(entrydate,1,10), "YMD")
format entrydate_d %td

* eligibility 
gen tps_eligible = 2021 if (entrydate_d <= td(09mar2021) & obs_perperson == 1)
replace tps_eligible = 2023 if (entrydate_d <= td(31jul2023) ///
							  & entrydate_d > td(09mar2021) ///
							  & obs_perperson == 1)
replace tps_eligible = 0 if entrydate_d > td(31jul2023)
replace tps_eligible = 0 if obs_perperson > 1 /* prior deportation = ineligible */
replace tps_eligible = . if entrydate_d == .



********************************************************************************
* Total number by TPS eligibility by week
********************************************************************************

* collapse to day
collapse (sum) totalremovals interiorremovals, by(tps_eligible departed_d)

* reshape
tostring tps_eligible, replace
replace tps_eligible = "Missing" if tps_eligible == "."
reshape wide totalremovals interiorremovals, i(departed_d) j(tps_eligible, string)

* create weeks
gen day_in_week = mod(departed_d - td(03oct2025), 7) + 1
gen week = floor((departed_d - td(03oct2025))/7) + 1

* collapse to weeks
gen days = 1
collapse (sum) total* interior* days (first) departed_d, by(week)


********************************************************************************
* graph
********************************************************************************

* total
gen totalinterior = interiorremovals0 + interiorremovals2021 ///
				   + interiorremovals2023 + interiorremovalsMissing
* Percent TPS2023
gen pct_TPS23 = interiorremovals2023 / totalinterior

* Also looking at the 2021 decision?
gen pct_statuslost = interiorremovals2023 / totalinterior if week < 6
replace pct_statuslost = (interiorremovals2023 + interiorremovals2021) / totalinterior ///
	        if week >= 6

* Percent Missing (to check that this is not driving the change)
gen missingpct = interiorremovalsMissing / totalinterior

* % TPS 2023 This is the graph in the paper
twoway connect pct_TPS23 week if week >= -35 & week <= 22 & totalinterior > 50, ///
	xline(0.5)
	
* also interesting
twoway connect pct_statuslost week if week >= -35 & week <= 22 & totalinterior > 50, ///
	xline(0.5)	

* % Missing
twoway connect missingpct week if week >= -35 & week <= 22 & totalinterior > 50, ///
	xline(0.5)

* Another way to look at this
twoway (connected interiorremovals2023 week if week >= -35 & week <= 22 & totalinterior > 50) ///
       (connected interiorremovals2021 week if week >= -35 & week <= 22 & totalinterior > 50) ///
	   (connected interiorremovals0 week if week >= -35 & week <= 22 & totalinterior > 50) ///
	   (connected interiorremovalsMissing week if week >= -35 & week <= 22 & totalinterior > 50), ///
	   xline(0.5) ///
	   legend(order(3 "Ineligible" 1 "TPS2023" 4 "Unknown" 2 "TPS2021"))
	

********************************************************************************
* End of do file
********************************************************************************
	
	
	
	