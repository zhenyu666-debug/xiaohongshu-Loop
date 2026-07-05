package com.getjobs.worker.utils;

import lombok.Data;

@Data
public class Job {
    private String jobId;
    private String jobTitle;
    private String jobName;
    private String companyName;
    private String companyId;
    private String location;
    private String salary;
    private String experience;
    private String degree;
    private String jobLink;
}
