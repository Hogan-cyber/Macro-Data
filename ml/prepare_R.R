# Run from repository root: Rscript ml/prepare_R.R
# Optional argument 1: local data directory or HTTPS directory.
# Base R only; no package installation or API key needed.
# Default inputs: market series. Macroeconomic native-frequency data remains available
# through load_macro(); its observation date MUST NOT be treated as release date.
load_macro <- function(base = "data") {
  base <- sub("/$", "", base)
  obs <- read.csv(paste0(base, "/observations.csv"), na.strings=c("", "NA"), stringsAsFactors=FALSE)
  meta <- read.csv(paste0(base, "/dictionary.csv"), stringsAsFactors=FALSE)
  obs$date <- as.Date(obs$date)
  stopifnot(!anyDuplicated(obs[c("series_id", "date")]), all(is.na(obs$value) == as.logical(obs$is_missing)))
  list(observations=obs, dictionary=meta)
}

make_weekly <- function(obs, cutoff=Sys.Date()) {
  ids <- c("NASDAQCOM","NASDAQ100","NASDAQSOX","SP500","DGS3MO","DGS2","DGS5","DGS10","DGS30","DFII10","T10Y2Y","T10Y3M","DFF","VIXCLS","DTWEXBGS","DEXCHUS","DCOILWTICO","DCOILBRENTEU","BAMLC0A0CM","BAMLH0A0HYM2")
  # Saturday through Friday weeks, labelled Friday; do not use the current unfinished week.
  friday <- function(x) x + ((5-as.POSIXlt(x)$wday) %% 7)
  weeks <- seq(friday(min(obs$date)), cutoff-1, by="7 days")
  out <- data.frame(date=weeks)
  for (id in ids) {
    r <- obs[obs$series_id==id & !is.na(obs$value), ]; r <- r[order(r$date), ]
    if (!nrow(r)) next
    r$week <- friday(r$date); r <- r[!duplicated(r$week, fromLast=TRUE), ]
    out[[id]] <- r$value[match(weeks, r$week)]
  }
  out
}

lag_value <- function(x,n) { if (n>=length(x)) return(rep(NA_real_,length(x))); c(rep(NA_real_,n),head(x,-n)) }
prepare_training <- function(weekly, target="NASDAQCOM", horizon=4L, out="ml/output/R") {
  stopifnot(target %in% names(weekly), horizon>0, horizon<nrow(weekly))
  prices <- c("NASDAQCOM","NASDAQ100","NASDAQSOX","SP500","DTWEXBGS","DEXCHUS")
  x <- data.frame(date=weekly$date)
  for (id in setdiff(names(weekly),"date")) {
    v <- weekly[[id]]
    if (id %in% prices) v <- 100*(v/lag_value(v,1)-1)
    x[[paste0(id,if (id %in% prices) "_return_1w" else "_level")]] <- v
    for (n in c(1,4,12)) x[[paste0(id,"_lag",n)]] <- lag_value(v,n)
    if (!id %in% prices) x[[paste0(id,"_change_1w")]] <- v-lag_value(v,1)
  }
  x$target <- 100*(c(tail(weekly[[target]],-horizon),rep(NA_real_,horizon))/weekly[[target]]-1)
  x$target_end <- c(tail(weekly$date,-horizon),rep(as.Date(NA),horizon))
  for (name in setdiff(names(x),c("date","target_end"))) x[[name]][!is.finite(x[[name]])] <- NA_real_
  x <- x[!is.na(x$target) & !is.na(weekly[[target]]), ];stopifnot(nrow(x)>=50)
  a <- floor(nrow(x)*.7)+1; b <- floor(nrow(x)*.85)+1
  train <- x[x$date<x$date[a] & x$target_end<x$date[a], ]
  validation <- x[x$date>=x$date[a] & x$date<x$date[b] & x$target_end<x$date[b], ]
  test <- x[x$date>=x$date[b], ]
  fields <- setdiff(names(x),c("date","target","target_end"))
  fields <- fields[vapply(train[fields],function(v) any(!is.na(v)),logical(1))]
  med <- vapply(train[fields],median,numeric(1),na.rm=TRUE)
  filled <- train[fields]
  for (f in fields) filled[[f]][is.na(filled[[f]])] <- med[f]
  means <- vapply(filled,mean,numeric(1)); scales <- vapply(filled,function(v) sqrt(mean((v-mean(v))^2)),numeric(1))
  scales[scales==0] <- 1
  dir.create(out,recursive=TRUE,showWarnings=FALSE)
  for (name in c("train","validation","test")) {
    part <- get(name); result <- data.frame(date=part$date)
    for (f in fields) {
      v <- part[[f]]; result[[paste0(f,"_missing")]] <- as.integer(is.na(v))
      v[is.na(v)] <- med[f];result[[f]] <- (v-means[f])/scales[f]
    }
    result$target <- part$target;result$target_end <- part$target_end
    write.csv(result,file.path(out,paste0(name,".csv")),row.names=FALSE,na="")
  }
  write.csv(data.frame(feature=fields,median=med,mean=means,std=scales),file.path(out,"preprocessing.csv"),row.names=FALSE)
  write.csv(weekly,file.path(out,"weekly_inputs.csv"),row.names=FALSE,na="")
  write.csv(x,file.path(out,"features_before_split.csv"),row.names=FALSE,na="")
  message(sprintf("Prepared %s train / %s validation / %s test weeks, %s features.",nrow(train),nrow(validation),nrow(test),length(fields)))
  invisible(list(train=train,validation=validation,test=test))
}

if (sys.nframe()==0L) {
  args <- commandArgs(trailingOnly=TRUE)
  dat <- load_macro(if(length(args)) args[1] else "data")
  # Native examples: subset(dat$observations, series_id=="PAYEMS_CHANGE")
  # CPI: CPI_YOY; unemployment: UNRATE; employment/population: EMRATIO.
  prepare_training(make_weekly(dat$observations))
}
