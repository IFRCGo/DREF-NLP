#library(arrow)
library(tidyverse)
#training_data<-read_feather(paste0(getwd(), "/data/Ops_learning_Dataset_codes.feather"))

pre_process<- function(dataset, added_info=FALSE){
  
  full_data <- dataset
  
  names(full_data) <- gsub("- ", "", names(full_data))
  names(full_data) <- gsub(" ", "_", names(full_data))
  names(full_data) <-tolower(names(full_data))
  
  names(full_data)
  
  small_data <- full_data %>% 
    select(modified_excerpt,
           dref_dimension, 
           dref_subdimension,
           dref_dimcode)
  
  dimension <- small_data %>% 
    group_by(modified_excerpt) %>% 
    summarise(dref_dimension=paste(dref_dimension, collapse = ", "),
              dref_dimcode=paste(dref_dimcode, collapse = ", ")) %>% 
    ungroup()
  
  
  full_data <- transform(full_data,id=as.numeric(factor(dref_dimcode)))
  
  tags_dict_dref <- full_data %>% 
    select(id, dref_subdimension) %>% 
    unique() %>% 
    mutate(id=id -1)
  
  
  write.table(tags_dict_dref, file = paste0(getwd(), "/data/training/tags_dict_dref.csv"), sep = "," , fileEncoding = "UTF-8")
  
  
  for (label in 1:41) {
    
    varname <- paste("id", label , sep="")
    
    full_data[[varname]] <- ifelse(full_data$id==label, 1, 0)
    
    
  }
  
  test <- full_data
  
  my_cols <- c("id1", "id2", "id3", "id4", "id5", "id6", "id7", "id8", "id9", "id10", "id11", "id12", "id13", "id14", "id15",
               "id16", "id17", "id18", "id19", "id20", "id21", "id22", "id23", "id24", "id25", "id26", "id27", "id28", "id29", "id30",
               "id31", "id32", "id33", "id34", "id35", "id36", "id37", "id38", "id39", "id40", "id41")   
  
  
  test$new_col <- do.call(paste, c(test[my_cols], sep = ""))
  
  subdimension <- full_data %>% 
    select(modified_excerpt,
           dref_dimension, 
           dref_subdimension,
           dref_dimcode, 
           id)%>% 
    group_by(modified_excerpt) %>% 
    #summarise(dref_subdimension=paste(dref_subdimension, collapse = ", "),
    #          dref_dimcode=paste(dref_dimcode, collapse = ", "),
    #          id =paste(id, collapse = ", ")) %>% 
    summarise(id = list(unique(id))) %>% 
    ungroup()
  
  for (n in 1:length(subdimension)) {
    
    
    
    for (label in 1:41) {
      
      varname <- paste("id", label , sep="")
      
      subdimension[[varname]][[n]] <- ifelse(label %in% subdimension[["id"]][[n]], 1, 0)
      
    }
  }
  
  
  subdimension <- subdimension %>% 
    rowwise() %>% 
    mutate(id1 =ifelse(1 %in% id, 1, 0)) %>% 
    mutate(id2 =ifelse(2 %in% id, 1, 0)) %>% 
    mutate(id3 =ifelse(3 %in% id, 1, 0)) %>% 
    mutate(id4 =ifelse(4 %in% id, 1, 0)) %>% 
    mutate(id5 =ifelse(5 %in% id, 1, 0)) %>% 
    mutate(id6 =ifelse(6 %in% id, 1, 0)) %>% 
    mutate(id7 =ifelse(7 %in% id, 1, 0)) %>% 
    mutate(id8 =ifelse(8 %in% id, 1, 0)) %>% 
    mutate(id9 =ifelse(9 %in% id, 1, 0)) %>% 
    mutate(id10 =ifelse(10 %in% id, 1, 0)) %>% 
    mutate(id11 =ifelse(11 %in% id, 1, 0)) %>% 
    mutate(id12 =ifelse(12 %in% id, 1, 0)) %>% 
    mutate(id13 =ifelse(13 %in% id, 1, 0)) %>% 
    mutate(id14 =ifelse(14 %in% id, 1, 0)) %>% 
    mutate(id15 =ifelse(15 %in% id, 1, 0)) %>% 
    mutate(id16 =ifelse(16 %in% id, 1, 0)) %>% 
    mutate(id17 =ifelse(17 %in% id, 1, 0)) %>% 
    mutate(id18 =ifelse(18 %in% id, 1, 0)) %>% 
    mutate(id19 =ifelse(19 %in% id, 1, 0)) %>% 
    mutate(id20 =ifelse(20 %in% id, 1, 0)) %>% 
    mutate(id21 =ifelse(21 %in% id, 1, 0)) %>% 
    mutate(id22 =ifelse(22 %in% id, 1, 0)) %>% 
    mutate(id23 =ifelse(23 %in% id, 1, 0)) %>% 
    mutate(id24 =ifelse(24 %in% id, 1, 0)) %>% 
    mutate(id25 =ifelse(25 %in% id, 1, 0)) %>% 
    mutate(id26 =ifelse(26 %in% id, 1, 0)) %>% 
    mutate(id27 =ifelse(27 %in% id, 1, 0)) %>% 
    mutate(id28 =ifelse(28 %in% id, 1, 0)) %>% 
    mutate(id29 =ifelse(29 %in% id, 1, 0)) %>% 
    mutate(id30 =ifelse(30 %in% id, 1, 0)) %>% 
    mutate(id31 =ifelse(31 %in% id, 1, 0)) %>% 
    mutate(id32 =ifelse(32 %in% id, 1, 0)) %>% 
    mutate(id33 =ifelse(33 %in% id, 1, 0)) %>% 
    mutate(id34 =ifelse(34 %in% id, 1, 0)) %>% 
    mutate(id35 =ifelse(35 %in% id, 1, 0)) %>% 
    mutate(id36 =ifelse(36 %in% id, 1, 0)) %>% 
    mutate(id37 =ifelse(37 %in% id, 1, 0)) %>% 
    mutate(id38 =ifelse(38 %in% id, 1, 0)) %>% 
    mutate(id39 =ifelse(39 %in% id, 1, 0)) %>% 
    mutate(id40 =ifelse(40 %in% id, 1, 0)) %>% 
    mutate(id41 =ifelse(41 %in% id, 1, 0)) 
  
  my_cols <- c("id1", "id2", "id3", "id4", "id5", "id6", "id7", "id8", "id9", "id10", "id11", "id12", "id13", "id14", "id15",
               "id16", "id17", "id18", "id19", "id20", "id21", "id22", "id23", "id24", "id25", "id26", "id27", "id28", "id29", "id30",
               "id31", "id32", "id33", "id34", "id35", "id36", "id37", "id38", "id39", "id40", "id41")   
  
  
  subdimension$Categories <- do.call(paste, c(subdimension[my_cols], sep = ""))
  
  #training_data <- transform(training_data,id=as.numeric(factor(DREF_DimCode)))
  #
  #subdimension_test <- subdimension %>% 
  #  mutate(dref_dimcode_test = as.factor(dref_dimcode)) %>% 
  #  mutate(dref_dimcode_test=as.numeric(as.character(dref_dimcode)))
  
  
  subdimension <- subdimension %>% 
    select(modified_excerpt,
           id, 
           Categories) %>% 
    rename(Excerpt =modified_excerpt) %>% 
    rename(Long = Excerpt)
  
  
  length <- dim(subdimension)[1]
  
  subdimension$Set <- numeric(nrow(subdimension))
  subdimension$Set[sample(nrow(subdimension), length/10)] <- 1
  
  subdimension_test <- subdimension %>% 
    filter(Set==1) %>% 
    mutate(Column1 = "test")
  
  subdimension_rest <- subdimension %>% 
    filter(Set==0)
  
  subdimension_rest$Set[sample(nrow(subdimension_rest), length/10)] <- 1
  
  subdimension_validation <- subdimension_rest %>% 
    filter(Set==1)%>% 
    mutate(Column1 = "validation")
  
  subdimension_train <- subdimension_rest %>% 
    filter(Set==0)%>% 
    mutate(Column1 = "training")
  
  subdimension <- subdimension_test %>% 
    bind_rows(subdimension_validation) %>% 
    bind_rows(subdimension_train) %>% 
    select(-id)
  
  subdimension <- subdimension %>% 
    select(Categories,
           Long, 
           everything())
  
  subdimension<- subdimension %>% 
    rename(Excerpt= Long,
           Long =Set,
           Set=Column1)
  
  library(stringr)
  
  subdimension <- subdimension %>% 
    mutate(Excerpt = str_replace_all(Excerpt, "[\r\n]" , " ") )
  
  if(added_info==TRUE){
    sector <- full_data %>% 
      select(modified_excerpt, dref_sector, hazard) 
    
    subdimension_sector <- subdimension %>% 
      inner_join(sector, by=c("Excerpt"="modified_excerpt")) %>% 
      mutate(Excerpt=paste(dref_sector, hazard, Excerpt, sep=". ")) %>% 
      select(Categories, Excerpt, Long, Set)
    
    write.table(subdimension_sector, file = paste0(getwd(), "/data/training/training_data_dref.csv"), sep = "\t" , fileEncoding = "UTF-8")
    
  }else{
    
    #write_csv(subdimension, file = paste0(getwd(), "/training_data_dref.csv"), delim = "\t")
    write.table(subdimension, file = paste0(getwd(), "/data/training/training_data_dref.csv"), sep = "\t" , fileEncoding = "UTF-8")
  }
  
  
}
